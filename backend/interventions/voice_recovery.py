"""
voice_recovery.py — Sarvam AI STT + Groq LLM voice recovery pipeline.
Accepts raw audio bytes, returns a structured VoiceResult.
"""
import uuid
import json
import logging
import httpx
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel
from groq import Groq
from backend.config import LLM_API_KEY, LLM_MODEL, STT_API_KEY, STT_BASE_URL, STT_MODEL
from backend.database import get_db_connection
from backend.audit import log_event

logger = logging.getLogger(__name__)
_groq = Groq(api_key=LLM_API_KEY)

VALID_INTENTS = {
    "PROMISE_TO_PAY", "PAYMENT_COMPLETED", "PAYMENT_PROBLEM",
    "DISPUTE", "CALLBACK_REQUEST", "REFUSAL", "WRONG_NUMBER",
    "NEEDS_ASSISTANCE", "OTHER",
}


class VoiceIntentResult(BaseModel):
    intent: str
    confidence: float
    promised_amount: Optional[float] = None
    promised_date: Optional[str] = None
    payment_status: str = ""
    requires_escalation: bool = False
    recommended_action: str = ""
    transcript: str = ""
    language: str = "hinglish"


def _transcribe_audio(audio_bytes: bytes, filename: str = "audio.wav") -> str:
    """Call Sarvam AI Saaras v3 STT endpoint, return transcript string."""
    if not STT_API_KEY:
        raise RuntimeError(
            "STT_API_KEY is not configured. Cannot transcribe audio. "
            "Set STT_API_KEY in your .env file."
        )

    headers = {"api-subscription-key": STT_API_KEY}
    files = {"file": (filename, audio_bytes, "audio/wav")}
    data = {"model": STT_MODEL, "language_code": "hi-IN"}

    try:
        resp = httpx.post(
            f"{STT_BASE_URL}/speech-to-text",
            headers=headers,
            files=files,
            data=data,
            timeout=30.0,
        )
    except httpx.TimeoutException as exc:
        raise RuntimeError(f"Sarvam STT timed out: {exc}") from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Sarvam STT network error: {exc}") from exc

    if resp.status_code != 200:
        raise RuntimeError(
            f"Sarvam STT returned HTTP {resp.status_code}: {resp.text[:300]}"
        )

    data_resp = resp.json()
    transcript = data_resp.get("transcript") or data_resp.get("text") or ""
    if not transcript:
        raise RuntimeError(f"Sarvam STT returned no transcript. Response: {data_resp}")

    return transcript


_INTENT_SYSTEM = """
You are an AI model analysing a Hinglish customer call transcript for an AI revenue recovery system.

Extract the customer's intent and any payment-related information. Return ONLY valid JSON with this schema:
{
  "intent": "<PROMISE_TO_PAY|PAYMENT_COMPLETED|PAYMENT_PROBLEM|DISPUTE|CALLBACK_REQUEST|REFUSAL|WRONG_NUMBER|NEEDS_ASSISTANCE|OTHER>",
  "confidence": <0.0 to 1.0>,
  "promised_amount": <number or null>,
  "promised_date": "<YYYY-MM-DD or null>",
  "payment_status": "<brief status description>",
  "requires_escalation": <true|false>,
  "recommended_action": "<what should RecoverAI do next?>"
}
Understand Hindi, English, and mixed Hinglish speech naturally.
"""


def _extract_intent(transcript: str) -> VoiceIntentResult:
    """Run Groq LLM on transcript to extract structured intent."""
    try:
        resp = _groq.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": _INTENT_SYSTEM},
                {"role": "user", "content": f"Transcript:\n{transcript}"},
            ],
            temperature=0.1,
            max_tokens=256,
        )
    except Exception as exc:
        raise RuntimeError(f"Groq intent extraction failed: {exc}") from exc

    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned invalid JSON for intent: {exc}\nRaw: {raw}") from exc

    intent = data.get("intent", "OTHER").upper()
    if intent not in VALID_INTENTS:
        intent = "OTHER"

    return VoiceIntentResult(
        intent=intent,
        confidence=float(data.get("confidence", 0.5)),
        promised_amount=data.get("promised_amount"),
        promised_date=data.get("promised_date"),
        payment_status=data.get("payment_status", ""),
        requires_escalation=bool(data.get("requires_escalation", False)),
        recommended_action=data.get("recommended_action", ""),
        transcript=transcript,
    )


def process_voice_audio(
    audio_bytes: bytes,
    recovery_case_id: str,
    customer_id: str,
    filename: str = "audio.wav",
) -> VoiceIntentResult:
    """
    Full voice recovery pipeline:
    1. STT (Sarvam AI)
    2. Intent extraction (Groq LLM)
    3. Persist to voice_recovery_sessions
    4. Audit log
    """
    now = datetime.now(timezone.utc).isoformat()
    session_id = f"vrs_{uuid.uuid4().hex[:10]}"

    # Step 1: Transcription — FAIL HARD if STT unavailable
    transcript = _transcribe_audio(audio_bytes, filename)

    # Step 2: Intent extraction
    result = _extract_intent(transcript)

    # Step 3: Persist
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO voice_recovery_sessions
              (id, recovery_case_id, customer_id, provider, transcript,
               language, detected_intent, confidence, extracted_amount,
               extracted_date, action_taken, started_at, completed_at)
            VALUES (?, ?, ?, 'sarvam_saaras_v3', ?, 'hinglish', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id, recovery_case_id, customer_id,
                transcript, result.intent, result.confidence,
                result.promised_amount, result.promised_date,
                result.recommended_action, now, now,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    log_event("voice_session", session_id, "VOICE_CALL_COMPLETED",
              f"Intent: {result.intent}, Confidence: {result.confidence:.0%}",
              {"case_id": recovery_case_id, "recommended_action": result.recommended_action})

    return result

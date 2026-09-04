"""
ai_decision.py — Groq LLM decision agent.
Takes structured case context and returns a validated Decision object.
"""
import json
import logging
from typing import Optional
from pydantic import BaseModel, field_validator
from groq import Groq
from backend.config import LLM_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)
_client = Groq(api_key=LLM_API_KEY)

VALID_DECISIONS = {
    "PAYMENT_RETRY", "PAYMENT_LINK", "EMAIL", "B2B_CHASER",
    "VOICE_CALL", "HINGLISH_VOICE", "PROMISE_TO_PAY", "ESCALATION", "STOP",
}
VALID_PRIORITIES = {"HIGH", "MEDIUM", "LOW"}


class Decision(BaseModel):
    decision: str
    priority: str
    reason: str
    next_action: str = ""
    requires_escalation: bool = False
    should_stop: bool = False
    promised_amount: Optional[float] = None
    promised_date: Optional[str] = None

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        if v.upper() not in VALID_DECISIONS:
            raise ValueError(f"Invalid decision: {v!r}. Must be one of {VALID_DECISIONS}")
        return v.upper()

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v.upper() not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority: {v!r}")
        return v.upper()


_SYSTEM_PROMPT = """
You are an AI recovery agent for reviveai, a revenue recovery platform.

Your job is to analyse a revenue-recovery case and decide the best recovery action.

IMPORTANT RULES:
- You must return ONLY valid JSON. No prose, no markdown, no ```json fences.
- The "decision" field must be exactly one of: PAYMENT_RETRY, PAYMENT_LINK, EMAIL,
  B2B_CHASER, VOICE_CALL, HINGLISH_VOICE, PROMISE_TO_PAY, ESCALATION, STOP
- The "priority" field must be exactly one of: HIGH, MEDIUM, LOW
- promised_amount and promised_date are only set when the decision is PROMISE_TO_PAY
- promised_date must be a valid ISO-8601 date string (YYYY-MM-DD)
- Recommend STOP only when recovery is genuinely impossible or harmful

Output schema:
{
  "decision": "<action>",
  "priority": "<HIGH|MEDIUM|LOW>",
  "reason": "<one sentence explanation>",
  "next_action": "<description of the next concrete step>",
  "requires_escalation": <true|false>,
  "should_stop": <true|false>,
  "promised_amount": <number or null>,
  "promised_date": "<YYYY-MM-DD or null>"
}
"""


def make_recovery_decision(case_context: dict) -> Decision:
    """
    Call Groq LLM with structured case context, validate output, return Decision.
    Raises ValueError if LLM returns malformed JSON or invalid fields.
    Raises RuntimeError on API failure.
    """
    prompt = f"Case context:\n{json.dumps(case_context, indent=2)}"

    try:
        response = _client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=512,
        )
    except Exception as exc:
        raise RuntimeError(f"Groq API call failed: {exc}") from exc

    raw = response.choices[0].message.content.strip()
    logger.debug("LLM raw response: %s", raw)

    # Strip any accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned invalid JSON: {exc}\nRaw: {raw}") from exc

    return Decision(**data)

from intelligence.diagnosis.rulesClassifier import classify_by_rules
import os
import json
from groq import Groq

# Initialize Groq client
client = None
if os.getenv("LLM_API_KEY"):
    client = Groq(api_key=os.getenv("LLM_API_KEY"))

def classify_error(error_code: str, error_description: str = "") -> dict:
    """
    Diagnoses root cause using rules first, and falls back to actual Groq LLM text classification.
    """
    # 1. Try exact rules classification first
    rule_match = classify_by_rules(error_code)
    if rule_match:
        return rule_match

    # 2. Fallback to actual LLM analysis on error_description
    if client:
        try:
            prompt = f"""
You are an expert AI payment recovery agent.
Analyze the following payment error and classify its root cause into exactly one of these categories:
- bank_timeout
- card_expired
- insufficient_balance
- user_abandoned
- unknown_technical_issue

Error Code: {error_code}
Error Description: {error_description}

Return ONLY a JSON object with this exact structure:
{{
    "root_cause": "category_name",
    "confidence": 0.0_to_1.0,
    "reasoning": "brief explanation"
}}
"""
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            response = json.loads(completion.choices[0].message.content)
            return {
                "root_cause": response.get("root_cause", "unknown_technical_issue"),
                "classifier_type": "groq_llm",
                "confidence_score": float(response.get("confidence", 0.85)),
                "reasoning": response.get("reasoning", "Classified by Groq AI")
            }
        except Exception as e:
            print(f"Groq API Error: {e}")
            pass # Fall back to heuristics if API fails

    # 3. Last resort fallback heuristic
    desc_lower = (error_description or "").lower()
    root_cause = "unknown_technical_issue"
    confidence = 0.70

    if "timeout" in desc_lower or "bank" in desc_lower:
        root_cause = "bank_timeout"
        confidence = 0.85
    elif "card" in desc_lower or "expired" in desc_lower:
        root_cause = "card_expired"
        confidence = 0.90
    elif "balance" in desc_lower or "fund" in desc_lower:
        root_cause = "insufficient_balance"
        confidence = 0.85
    elif "dismiss" in desc_lower or "closed" in desc_lower:
        root_cause = "user_abandoned"
        confidence = 0.88

    return {
        "root_cause": root_cause,
        "classifier_type": "llm_fallback",
        "confidence_score": confidence,
        "reasoning": f"LLM/heuristic analysis based on description: '{error_description}'"
    }

# app/executors/voice_executor.py

def initiate_voice_call(
    customer_id,
    playbook,
    amount,
    currency,
    language
):
    print(
        f"Voice call → {customer_id} | "
        f"{playbook} | {amount} {currency} | "
        f"language={language}"
    )
    return "voice_call_started"
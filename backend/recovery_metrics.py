"""
metrics.py — real KPI aggregation from the database.
All figures are derived from actual DB records, never hardcoded.
"""
from backend.database import get_db_connection


def compute_recovery_metrics() -> dict:
    conn = get_db_connection()
    try:
        # Revenue at risk totals
        rar = conn.execute(
            """
            SELECT
              COUNT(*) as total_cases,
              COALESCE(SUM(amount_at_risk), 0) as total_revenue_at_risk,
              COUNT(CASE WHEN risk_status = 'open' THEN 1 END) as open_cases,
              COUNT(CASE WHEN risk_status = 'resolved' THEN 1 END) as resolved_cases
            FROM revenue_at_risk
            """
        ).fetchone()

        # Recovery cases
        cases = conn.execute(
            """
            SELECT
              COUNT(*) as total_recovery_cases,
              COALESCE(SUM(attempt_count), 0) as total_attempts,
              COUNT(CASE WHEN status = 'recovered' THEN 1 END) as successful_recoveries,
              COALESCE(SUM(CASE WHEN status = 'recovered' THEN amount_recovered ELSE 0 END), 0) as total_recovered_amount,
              COALESCE(SUM(CASE WHEN status NOT IN ('recovered','stopped','failed') THEN amount_at_risk ELSE 0 END), 0) as outstanding_revenue,
              COUNT(CASE WHEN escalation_level > 0 THEN 1 END) as escalated_cases
            FROM recovery_cases
            """
        ).fetchone()

        # Customers contacted
        contacts = conn.execute(
            "SELECT COUNT(DISTINCT customer_id) as customers_contacted FROM recovery_actions WHERE status = 'executed'"
        ).fetchone()

        # Promise stats
        promises = conn.execute(
            """
            SELECT
              COUNT(*) as total_promises,
              COUNT(CASE WHEN status = 'pending' THEN 1 END) as active_promises,
              COUNT(CASE WHEN status = 'overdue' THEN 1 END) as overdue_promises,
              COUNT(CASE WHEN status = 'fulfilled' THEN 1 END) as fulfilled_promises,
              COALESCE(SUM(CASE WHEN status = 'fulfilled' THEN promised_amount ELSE 0 END), 0) as fulfilled_amount
            FROM promise_to_pay
            """
        ).fetchone()

        # Recovery by intervention type
        by_action = conn.execute(
            """
            SELECT ra.action_type,
                   COUNT(*) as count,
                   COALESCE(SUM(rc.amount_recovered), 0) as attributed_recovered
            FROM recovery_actions ra
            LEFT JOIN recovery_cases rc ON rc.id = ra.recovery_case_id AND rc.status = 'recovered'
            GROUP BY ra.action_type
            """
        ).fetchall()

        total_at_risk = float(rar["total_revenue_at_risk"] or 0)
        total_recovered = float(cases["total_recovered_amount"] or 0)
        recovery_rate = round((total_recovered / total_at_risk * 100), 2) if total_at_risk > 0 else 0.0

    finally:
        conn.close()

    return {
        "revenue_at_risk": total_at_risk,
        "total_cases": int(rar["total_cases"] or 0),
        "open_cases": int(rar["open_cases"] or 0),
        "resolved_cases": int(rar["resolved_cases"] or 0),
        "total_recovery_cases": int(cases["total_recovery_cases"] or 0),
        "total_attempts": int(cases["total_attempts"] or 0),
        "customers_contacted": int(contacts["customers_contacted"] or 0),
        "successful_recoveries": int(cases["successful_recoveries"] or 0),
        "total_recovered_amount": total_recovered,
        "recovery_rate_pct": recovery_rate,
        "outstanding_revenue": float(cases["outstanding_revenue"] or 0),
        "escalated_cases": int(cases["escalated_cases"] or 0),
        "active_promises": int(promises["active_promises"] or 0),
        "overdue_promises": int(promises["overdue_promises"] or 0),
        "fulfilled_promises": int(promises["fulfilled_promises"] or 0),
        "fulfilled_promise_amount": float(promises["fulfilled_amount"] or 0),
        "recovered_amount_by_intervention": [
            {
                "action_type": row["action_type"],
                "count": int(row["count"]),
                "attributed_recovered": float(row["attributed_recovered"] or 0),
            }
            for row in by_action
        ],
    }

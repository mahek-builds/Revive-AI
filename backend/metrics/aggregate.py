from backend.database import get_db_connection

def compute_aggregate_metrics() -> dict:
    """Calculates summary revenue recovery metrics for dashboard."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Sum total revenue at risk
    cursor.execute("SELECT SUM(amount) AS total FROM revenue_at_risk")
    total_risk_row = cursor.fetchone()
    total_risk = float(total_risk_row["total"]) if total_risk_row and total_risk_row["total"] is not None else 0.0

    # Sum recovered revenue
    cursor.execute("SELECT SUM(amount) AS total FROM revenue_at_risk WHERE status = 'recovered'")
    total_rec_row = cursor.fetchone()
    total_recovered = float(total_rec_row["total"]) if total_rec_row and total_rec_row["total"] is not None else 0.0

    # Count pending interventions
    cursor.execute("SELECT COUNT(*) AS count FROM interventions WHERE status = 'pending'")
    pending_row = cursor.fetchone()
    pending_count = int(pending_row["count"]) if pending_row and pending_row["count"] is not None else 0

    # Calculate recovery rate percentage
    recovery_rate = (total_recovered / total_risk * 100.0) if total_risk > 0 else 0.0

    conn.close()

    return {
        "total_revenue_at_risk": round(total_risk, 2),
        "recovered_revenue": round(total_recovered, 2),
        "recovery_rate_percent": round(recovery_rate, 2),
        "pending_interventions": pending_count
    }

"""SQL-backed data sources for the Vygor demo chat."""
import warehouse
from datetime import datetime

def studio_summary():
    """Compact text snapshot of all data — injected into the system prompt.
    Queries the curated views directly to provide context to the AI."""
    try:
        # 1. Memberships breakdown
        plans_rows = warehouse.run_query(
            "SELECT plan_name, COUNT(*) as count FROM vw_memberships "
            "WHERE state = 'active' GROUP BY 1 ORDER BY 2 DESC"
        )
        
        # 2. Active vs Cancelled
        status_rows = warehouse.run_query(
            "SELECT state, COUNT(*) as count FROM vw_memberships GROUP BY 1"
        )
        
        # 3. Top classes
        class_rows = warehouse.run_query(
            "SELECT class_name, COUNT(*) as count FROM vw_class_attendance "
            "WHERE status = 'confirmed' AND checked_in_at IS NOT NULL "
            "GROUP BY 1 ORDER BY 2 DESC LIMIT 5"
        )
        
        # 4. Busiest times (approximate from check-ins)
        time_rows = warehouse.run_query(
            "SELECT strftime('%H:00', start_at) as hr, COUNT(*) as count "
            "FROM vw_class_attendance WHERE status = 'confirmed' AND checked_in_at IS NOT NULL "
            "GROUP BY 1 ORDER BY 2 DESC LIMIT 5"
        )

        # 5. Recent signups trend
        signup_rows = warehouse.run_query(
            "SELECT strftime('%Y-%m', purchased_at) as month, COUNT(*) as count "
            "FROM vw_memberships WHERE purchased_at IS NOT NULL "
            "GROUP BY 1 ORDER BY 1 DESC LIMIT 6"
        )

        active_count = sum(r['count'] for r in status_rows if r['state'] == 'active')
        cancelled_count = sum(r['count'] for r in status_rows if r['state'] == 'cancelled')
        total_records = active_count + cancelled_count

        lines = [
            f"Total membership records: {total_records}  ·  "
            f"Active: {active_count}  ·  Cancelled: {cancelled_count}",
            "Active members by plan: " + ", ".join(
                f"{r['plan_name']} ({r['count']})" for r in plans_rows
            ),
            "Top classes by check-ins: " + ", ".join(
                f"{r['class_name']} ({r['count']})" for r in class_rows
            ),
            "Busiest check-in hours: " + ", ".join(
                f"{r['hr']} ({r['count']})" for r in time_rows
            ),
            "Recent signups by month: " + ", ".join(
                f"{r['month']}={r['count']}" for r in reversed(signup_rows)
            ),
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"Summary unavailable: {e}"

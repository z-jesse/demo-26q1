import subprocess
import os
import sys
from pathlib import Path

DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    sys.exit("DATABASE_URL is not set. Add it to .env or export it in your shell.")
DATA_DIR = Path("data")

# Core tables to export for the demo warehouse
QUERIES = {
    "customers_raw.csv": """
        SELECT cp.public_id, u.first_name, u.last_name, u.email, u.phone, u.created_at AS signed_up_at
        FROM customer_profiles cp
        JOIN users u ON u.id = cp.user_id
        WHERE cp.organization_id = 2
    """,
    "membership_plans_raw.csv": """
        SELECT name, price_cents, class_limit
        FROM membership_plans
        WHERE organization_id = 2
    """,
    "memberships_raw.csv": """
        SELECT cp.public_id AS customer_public_id, mp.name AS plan_name, m.purchased_at, m.activated_at, m.cancelled_at, m.expires_at
        FROM memberships m
        JOIN membership_plans mp ON mp.id = m.membership_plan_id
        JOIN customer_profiles cp ON cp.id = m.customer_profile_id
        WHERE cp.organization_id = 2
        AND m.purchased_at IS NOT NULL
        AND m.failed_at IS NULL
    """,
    "instructors_raw.csv": """
        SELECT u.first_name, u.last_name, u.email
        FROM staff_profiles sp
        JOIN users u ON u.id = sp.user_id
        WHERE sp.organization_id = 2
    """,
    "class_templates_raw.csv": """
        SELECT name
        FROM bookable_templates
        WHERE organization_id = 2
    """,
    "bookings_raw.csv": """
        SELECT 
            cp.public_id AS customer_public_id,
            bt.name AS class_template_name,
            u.first_name || ' ' || u.last_name AS instructor_name,
            b.start_at,
            b.end_at,
            bk.status,
            bk.checked_in_at,
            bk.cancelled_at,
            bk.purchased_at,
            bt.price_cents,
            (CASE WHEN bk.payment_source_type = 'Membership' THEN 1 ELSE 0 END) AS paid_with_membership
        FROM bookings bk
        JOIN customer_profiles cp ON cp.id = bk.customer_profile_id
        JOIN bookables b ON b.id = bk.bookable_id
        JOIN bookable_templates bt ON bt.id = b.bookable_template_id
        LEFT JOIN staff_profiles sp ON sp.id = b.staff_profile_id
        LEFT JOIN users u ON u.id = sp.user_id
        WHERE cp.organization_id = 2
        AND b.start_at > '2025-01-01'
    """
}

def run_export(query, output_path):
    # Format query for \copy: single line, no trailing semicolon
    query_clean = ' '.join(query.strip().rstrip(';').split())
    path_str = str(output_path.resolve()).replace('\\', '/')
    
    cmd = f"\\copy ({query_clean}) TO '{path_str}' WITH CSV HEADER;"
    
    result = subprocess.run(
        ['psql', DB_URL],
        input=cmd,
        text=True,
        capture_output=True,
    )
    return result

def main():
    DATA_DIR.mkdir(exist_ok=True)
    
    print(f"Exporting raw tables to {DATA_DIR}...")
    
    for filename, query in QUERIES.items():
        output_path = DATA_DIR / filename
        print(f"  -> {filename} ... ", end='', flush=True)
        
        result = run_export(query, output_path)
        
        if result.returncode == 0 and 'COPY' in result.stdout:
            print("OK")
        else:
            print("FAILED")
            err = (result.stderr or result.stdout).strip()
            if err:
                print(f"    {err}")

if __name__ == "__main__":
    main()

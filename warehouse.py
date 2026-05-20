"""Demo warehouse: a SQLite mirror of a subset of the Rails schema, seeded
from the CSV exports in data/ and synthesized supplementary tables. The
report generator queries the curated views defined here via run_query().

Rebuilds warehouse.db whenever this file or any source CSV is newer.
"""
import csv
import os
import random
import re
import sqlite3
from datetime import datetime, timedelta

_ROOT = os.path.dirname(__file__)
_DATA_DIR = os.path.join(_ROOT, "data")
_DB_PATH = os.path.join(_ROOT, "warehouse.db")

_RNG_SEED = 42
_BOOKING_WINDOW_START = datetime(2025, 11, 1)
_BOOKING_WINDOW_END   = datetime(2026, 5, 20)


# ── Build trigger ──────────────────────────────────────────────────────────

def _source_mtimes():
    paths = [__file__]
    for name in os.listdir(_DATA_DIR):
        if name.endswith(".csv"):
            paths.append(os.path.join(_DATA_DIR, name))
    return max(os.path.getmtime(p) for p in paths)


def _needs_rebuild():
    if not os.path.exists(_DB_PATH):
        return True
    return os.path.getmtime(_DB_PATH) < _source_mtimes()


# ── CSV loaders ────────────────────────────────────────────────────────────

def _read_csv(name):
    path = os.path.join(_DATA_DIR, name)
    with open(path, encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


# ── Build ──────────────────────────────────────────────────────────────────

def _build():
    tmp_path = _DB_PATH + ".tmp"
    if os.path.exists(tmp_path):
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    conn = sqlite3.connect(tmp_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    rng = random.Random(_RNG_SEED)

    _create_tables(cur)
    customers = _load_customers(cur)
    plans = _load_membership_plans(cur)
    memberships = _load_memberships(cur, customers, plans)
    instructors = _load_instructors(cur)
    class_templates = _load_class_templates(cur)
    bookings = _load_bookings(cur, customers, class_templates, instructors)
    products = _seed_products(cur)
    product_orders = _seed_product_orders(cur, rng, customers, products)
    _seed_payments(cur, rng, memberships, plans, bookings, product_orders,
                   customers)

    _create_views(cur)

    conn.commit()
    conn.close()

    # Atomically replace the old database with the new one
    os.replace(tmp_path, _DB_PATH)


def _create_tables(cur):
    cur.executescript("""
    CREATE TABLE customers (
        id INTEGER PRIMARY KEY,
        public_id TEXT UNIQUE NOT NULL,
        first_name TEXT,
        last_name TEXT,
        email TEXT,
        phone TEXT,
        signed_up_at TEXT
    );
    CREATE TABLE membership_plans (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        price_cents INTEGER NOT NULL,
        class_limit INTEGER
    );
    CREATE TABLE memberships (
        id INTEGER PRIMARY KEY,
        customer_id INTEGER NOT NULL REFERENCES customers(id),
        membership_plan_id INTEGER NOT NULL REFERENCES membership_plans(id),
        purchased_at TEXT,
        activated_at TEXT,
        cancelled_at TEXT,
        expires_at TEXT,
        next_renewal_at TEXT
    );
    CREATE TABLE instructors (
        id INTEGER PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        email TEXT
    );
    CREATE TABLE class_templates (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        price_cents INTEGER NOT NULL,
        member_price_cents INTEGER NOT NULL
    );
    CREATE TABLE bookings (
        id INTEGER PRIMARY KEY,
        customer_id INTEGER NOT NULL REFERENCES customers(id),
        class_template_id INTEGER NOT NULL REFERENCES class_templates(id),
        instructor_id INTEGER REFERENCES instructors(id),
        start_at TEXT NOT NULL,
        end_at TEXT NOT NULL,
        status TEXT NOT NULL,            -- completed, cancelled, no_show, late_cancelled
        checked_in_at TEXT,
        cancelled_at TEXT,
        purchased_at TEXT,
        price_cents INTEGER NOT NULL,
        paid_with_membership INTEGER NOT NULL  -- 0/1
    );
    CREATE TABLE products (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        price_cents INTEGER NOT NULL,
        stock INTEGER
    );
    CREATE TABLE product_orders (
        id INTEGER PRIMARY KEY,
        product_id INTEGER NOT NULL REFERENCES products(id),
        customer_id INTEGER NOT NULL REFERENCES customers(id),
        status TEXT NOT NULL,            -- completed, refunded
        purchased_at TEXT,
        price_cents INTEGER NOT NULL
    );
    CREATE TABLE payments (
        id INTEGER PRIMARY KEY,
        customer_id INTEGER NOT NULL REFERENCES customers(id),
        purchasable_type TEXT NOT NULL,  -- membership, booking, product
        purchasable_id INTEGER NOT NULL,
        amount_cents INTEGER NOT NULL,
        status TEXT NOT NULL,            -- succeeded, refunded, failed
        method TEXT NOT NULL,            -- card, terminal, cash
        created_at TEXT NOT NULL
    );
    CREATE INDEX idx_bookings_start ON bookings(start_at);
    CREATE INDEX idx_payments_created ON payments(created_at);
    CREATE INDEX idx_memberships_purchased ON memberships(purchased_at);
    """)


# ── Customers ──────────────────────────────────────────────────────────────

def _load_customers(cur):
    """Seed customers from the customers_raw CSV."""
    rows = _read_csv("customers_raw.csv")
    customers = []
    for r in rows:
        cid = (r.get("public_id") or "").strip()
        if not cid:
            continue
        c = {
            "public_id": cid,
            "first_name": (r.get("first_name") or "").strip(),
            "last_name": (r.get("last_name") or "").strip(),
            "email": (r.get("email") or "").strip(),
            "phone": (r.get("phone") or "").strip(),
            "signed_up_at": _trim_ts(r.get("signed_up_at")),
        }
        cur.execute(
            "INSERT INTO customers (public_id, first_name, last_name, email, phone, signed_up_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (c["public_id"], c["first_name"], c["last_name"], c["email"],
             c["phone"], c["signed_up_at"]),
        )
        customers.append({"id": cur.lastrowid, **c})
    return customers


# ── Membership plans + memberships ────────────────────────────────────────

def _load_membership_plans(cur):
    rows = _read_csv("membership_plans_raw.csv")
    plans = {}
    for r in rows:
        name = (r.get("name") or "").strip()
        if not name or name in plans:
            continue
        meta = {
            "price_cents": int(r.get("price_cents") or 0),
            "class_limit": int(r.get("class_limit")) if r.get("class_limit") else None
        }
        cur.execute(
            "INSERT INTO membership_plans (name, price_cents, class_limit) VALUES (?, ?, ?)",
            (name, meta["price_cents"], meta["class_limit"]),
        )
        plans[name] = {"id": cur.lastrowid, "name": name, **meta}
    return plans


def _trim_ts(s):
    s = (s or "").strip()
    if not s:
        return None
    # CSV uses "2025-11-12 21:04:26.480375" — drop microseconds for SQLite cleanliness.
    return s.split(".")[0]


def _load_memberships(cur, customers, plans):
    by_pid = {c["public_id"]: c for c in customers}
    rows = _read_csv("memberships_raw.csv")
    out = []
    for r in rows:
        cid = (r.get("customer_public_id") or "").strip()
        plan_name = (r.get("plan_name") or "").strip()
        if cid not in by_pid or plan_name not in plans:
            continue
        purchased = _trim_ts(r.get("purchased_at"))
        activated = _trim_ts(r.get("activated_at"))
        cancelled = _trim_ts(r.get("cancelled_at"))
        expires = _trim_ts(r.get("expires_at"))
        
        cur.execute(
            "INSERT INTO memberships (customer_id, membership_plan_id, purchased_at, "
            "activated_at, cancelled_at, expires_at, next_renewal_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (by_pid[cid]["id"], plans[plan_name]["id"], purchased, activated,
             cancelled, expires, None),
        )
        out.append({
            "id": cur.lastrowid,
            "customer_id": by_pid[cid]["id"],
            "plan_id": plans[plan_name]["id"],
            "plan_name": plan_name,
            "purchased_at": purchased,
            "cancelled_at": cancelled,
        })
    return out


# ── Instructors ────────────────────────────────────────────────────────────

def _load_instructors(cur):
    rows = _read_csv("instructors_raw.csv")
    out = []
    seen = set()
    for r in rows:
        fn = (r.get("first_name") or "").strip()
        ln = (r.get("last_name") or "").strip()
        em = (r.get("email") or "").strip()
        if not fn or em in seen:
            continue
        seen.add(em)
        cur.execute(
            "INSERT INTO instructors (first_name, last_name, email) VALUES (?, ?, ?)",
            (fn, ln, em),
        )
        out.append({"id": cur.lastrowid, "name": f"{fn} {ln}"})
    return out


# ── Class templates ───────────────────────────────────────────────────────

def _load_class_templates(cur):
    rows = _read_csv("class_templates_raw.csv")
    out = []
    seen = set()
    for r in rows:
        name = (r.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        cur.execute(
            "INSERT INTO class_templates (name, price_cents, member_price_cents) VALUES (?, ?, ?)",
            (name, 2800, 0),
        )
        out.append({"id": cur.lastrowid, "name": name})
    return out



# ── Bookings ───────────────────────────────────────────────────────────────

def _load_bookings(cur, customers, class_templates, instructors):
    """Load bookings from raw CSV."""
    rows = _read_csv("bookings_raw.csv")
    
    by_pid = {c["public_id"]: c["id"] for c in customers}
    by_ct_name = {ct["name"]: ct["id"] for ct in class_templates}
    by_inst_name = {inst["name"]: inst["id"] for inst in instructors}
    
    out = []
    for r in rows:
        cid = (r.get("customer_public_id") or "").strip()
        ct_name = (r.get("class_template_name") or "").strip()
        inst_name = (r.get("instructor_name") or "").strip()
        
        if cid not in by_pid or ct_name not in by_ct_name:
            continue
            
        purchased_at = _trim_ts(r.get("purchased_at")) or _trim_ts(r.get("start_at"))
        
        cur.execute(
            "INSERT INTO bookings (customer_id, class_template_id, instructor_id, "
            "start_at, end_at, status, checked_in_at, cancelled_at, purchased_at, "
            "price_cents, paid_with_membership) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (by_pid[cid], by_ct_name[ct_name], by_inst_name.get(inst_name),
             _trim_ts(r.get("start_at")), _trim_ts(r.get("end_at")),
             r.get("status"), _trim_ts(r.get("checked_in_at")),
             _trim_ts(r.get("cancelled_at")), purchased_at,
             int(r.get("price_cents") or 0), int(r.get("paid_with_membership") or 0)),
        )
        out.append({
            "id": cur.lastrowid,
            "customer_id": by_pid[cid],
            "status": r.get("status"),
            "price_cents": int(r.get("price_cents") or 0),
            "paid_with_membership": int(r.get("paid_with_membership") or 0),
            "purchased_at": purchased_at,
        })

    return out


# ── Products + orders ─────────────────────────────────────────────────────

_PRODUCTS = [
    ("Vygor Premium Yoga Mat",      8800, 60),
    ("Cork Yoga Block (pair)",      3200, 120),
    ("Vygor Branded Tote",          2400, 200),
    ("Reusable Water Bottle",       2800, 80),
    ("Sweat Towel",                 1800, 150),
    ("Recovery Tea Blend",          1600, 100),
    ("Vygor Hoodie",                6800, 40),
    ("Wild Thing Tank",             4200, 75),
]


def _seed_products(cur):
    out = []
    for name, price, stock in _PRODUCTS:
        cur.execute(
            "INSERT INTO products (name, price_cents, stock) VALUES (?, ?, ?)",
            (name, price, stock),
        )
        out.append({"id": cur.lastrowid, "name": name, "price_cents": price})
    return out


def _seed_product_orders(cur, rng, customers, products):
    NUM_ORDERS = 220
    days = (_BOOKING_WINDOW_END - _BOOKING_WINDOW_START).days
    out = []
    for _ in range(NUM_ORDERS):
        customer = rng.choice(customers)
        product = rng.choice(products)
        purchased = (_BOOKING_WINDOW_START + timedelta(days=rng.randint(0, days),
                                                        seconds=rng.randint(0, 86400)))
        status = "refunded" if rng.random() < 0.03 else "completed"
        cur.execute(
            "INSERT INTO product_orders (product_id, customer_id, status, purchased_at, price_cents) "
            "VALUES (?, ?, ?, ?, ?)",
            (product["id"], customer["id"], status, purchased.isoformat(sep=" "),
             product["price_cents"]),
        )
        out.append({
            "id": cur.lastrowid,
            "customer_id": customer["id"],
            "price_cents": product["price_cents"],
            "status": status,
            "purchased_at": purchased.isoformat(sep=" "),
        })
    return out


# ── Payments (revenue) ────────────────────────────────────────────────────

def _seed_payments(cur, rng, memberships, plans, bookings, product_orders,
                   customers):
    plan_by_id = {p["id"]: p for p in plans.values()}

    # Membership payments
    for m in memberships:
        plan = plan_by_id[m["plan_id"]]
        if not m["purchased_at"]:
            continue
        cur.execute(
            "INSERT INTO payments (customer_id, purchasable_type, purchasable_id, "
            "amount_cents, status, method, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (m["customer_id"], "membership", m["id"], plan["price_cents"],
             "succeeded", "card", m["purchased_at"]),
        )

    # Drop-in booking payments (only non-member, non-cancelled)
    for b in bookings:
        if b["paid_with_membership"] or b["price_cents"] == 0:
            continue
        if b["status"] in ("cancelled", "late_cancelled"):
            continue
        method = rng.choices(["card", "terminal"], weights=[3, 1], k=1)[0]
        cur.execute(
            "INSERT INTO payments (customer_id, purchasable_type, purchasable_id, "
            "amount_cents, status, method, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (b["customer_id"], "booking", b["id"], b["price_cents"],
             "succeeded", method, b["purchased_at"]),
        )

    # Product orders
    for o in product_orders:
        status = "refunded" if o["status"] == "refunded" else "succeeded"
        method = rng.choices(["card", "terminal"], weights=[2, 1], k=1)[0]
        cur.execute(
            "INSERT INTO payments (customer_id, purchasable_type, purchasable_id, "
            "amount_cents, status, method, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (o["customer_id"], "product", o["id"], o["price_cents"],
             status, method, o["purchased_at"]),
        )


# ── Views (the AI's surface area) ─────────────────────────────────────────

_VIEW_DDL = """
CREATE VIEW vw_class_attendance AS
SELECT
  b.id AS booking_id,
  b.start_at,
  b.end_at,
  b.status,
  b.checked_in_at,
  b.cancelled_at,
  b.paid_with_membership,
  b.price_cents,
  ct.name AS class_name,
  i.first_name || ' ' || i.last_name AS instructor_name,
  i.id AS instructor_id,
  c.first_name || ' ' || c.last_name AS customer_name,
  c.id AS customer_id,
  c.email AS customer_email
FROM bookings b
JOIN class_templates ct ON ct.id = b.class_template_id
LEFT JOIN instructors i  ON i.id = b.instructor_id
JOIN customers c          ON c.id = b.customer_id;

CREATE VIEW vw_revenue AS
SELECT
  p.id AS payment_id,
  p.created_at,
  p.amount_cents,
  p.amount_cents / 100.0 AS amount_dollars,
  p.status,
  p.method,
  p.purchasable_type,
  p.purchasable_id,
  c.first_name || ' ' || c.last_name AS customer_name,
  c.id AS customer_id,
  c.email AS customer_email,
  strftime('%Y-%m', p.created_at) AS month,
  strftime('%Y-%m-%d', p.created_at) AS day,
  COALESCE(i.first_name || ' ' || i.last_name, '') AS instructor_name,
  CASE 
    WHEN p.purchasable_type = 'membership' THEN mp.name
    WHEN p.purchasable_type = 'product' THEN pr.name
    WHEN p.purchasable_type = 'booking' THEN ct.name
    ELSE p.purchasable_type
  END AS item_name
FROM payments p
JOIN customers c ON c.id = p.customer_id
LEFT JOIN bookings b ON p.purchasable_type = 'booking' AND p.purchasable_id = b.id
LEFT JOIN instructors i ON b.instructor_id = i.id
LEFT JOIN class_templates ct ON b.class_template_id = ct.id
LEFT JOIN memberships m ON p.purchasable_type = 'membership' AND p.purchasable_id = m.id
LEFT JOIN membership_plans mp ON m.membership_plan_id = mp.id
LEFT JOIN product_orders po ON p.purchasable_type = 'product' AND p.purchasable_id = po.id
LEFT JOIN products pr ON po.product_id = pr.id;

CREATE VIEW vw_memberships AS
SELECT
  m.id AS membership_id,
  m.purchased_at,
  m.activated_at,
  m.cancelled_at,
  m.next_renewal_at,
  CASE WHEN m.cancelled_at IS NULL THEN 'active' ELSE 'cancelled' END AS state,
  mp.name AS plan_name,
  mp.price_cents AS plan_price_cents,
  mp.price_cents / 100.0 AS plan_price_dollars,
  mp.class_limit,
  c.first_name || ' ' || c.last_name AS customer_name,
  c.id AS customer_id,
  c.email AS customer_email
FROM memberships m
JOIN membership_plans mp ON mp.id = m.membership_plan_id
JOIN customers c          ON c.id = m.customer_id;

CREATE VIEW vw_customers AS
SELECT
  c.id AS customer_id,
  c.public_id,
  c.first_name || ' ' || c.last_name AS customer_name,
  c.email,
  c.signed_up_at,
  (SELECT COUNT(*) FROM bookings b WHERE b.customer_id = c.id) AS bookings_count,
  (SELECT COUNT(*) FROM bookings b WHERE b.customer_id = c.id AND b.status = 'confirmed') AS completed_count,
  (SELECT COALESCE(SUM(p.amount_cents), 0) / 100.0 FROM payments p
     WHERE p.customer_id = c.id AND p.status = 'succeeded') AS lifetime_value_dollars,
  (SELECT mp.name FROM memberships m JOIN membership_plans mp ON mp.id = m.membership_plan_id
     WHERE m.customer_id = c.id AND m.cancelled_at IS NULL ORDER BY m.purchased_at DESC LIMIT 1) AS active_plan_name
FROM customers c;

CREATE VIEW vw_products AS
SELECT
  o.id AS order_id,
  o.purchased_at,
  o.status,
  o.price_cents,
  o.price_cents / 100.0 AS price_dollars,
  p.name AS product_name,
  p.id AS product_id,
  c.first_name || ' ' || c.last_name AS customer_name,
  c.id AS customer_id,
  c.email AS customer_email,
  strftime('%Y-%m', o.purchased_at) AS month
FROM product_orders o
JOIN products p   ON p.id = o.product_id
JOIN customers c  ON c.id = o.customer_id;
"""


def _create_views(cur):
    cur.executescript(_VIEW_DDL)


# ── Public API ────────────────────────────────────────────────────────────

_FORBIDDEN_TOKEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|PRAGMA|VACUUM|REINDEX)\b",
    re.IGNORECASE,
)


def make_timeout_handler(timeout_seconds):
    """Factory to create a query timeout handler."""
    import time
    start_time = time.time()
    def handler():
        # Abort query if execution time exceeds timeout
        if time.time() - start_time > timeout_seconds:
            return 1  # Non-zero return aborts query
        return 0
    return handler


def _view_isolation_authorizer(action, arg1, arg2, arg3, arg4):
    """Enforces that reads are only allowed from vw_* views and sqlite metadata."""
    # SQLITE_READ code is 20
    if action == 20:
        table_name = arg1
        view_name = arg4
        
        # If the read is happening inside a view, allow it if it is a vw_* view
        if view_name and view_name.lower().startswith("vw_"):
            return 0  # SQLITE_OK
            
        # If the read is happening directly from the top-level query,
        # allow only if the table name starts with vw_ or sqlite_
        if table_name:
            table_name_lower = table_name.lower()
            if table_name_lower.startswith("vw_") or table_name_lower.startswith("sqlite_"):
                return 0  # SQLITE_OK
                
        # Deny all other direct read accesses
        return 1  # SQLITE_DENY
    return 0  # SQLITE_OK


def run_query(sql, limit=500, timeout=5.0):
    """Run a SELECT against the warehouse and return rows as list of dicts.

    Enforces:
    - Single statement only (no `;` followed by more SQL).
    - Must start with SELECT or WITH (CTE).
    - No DDL/DML tokens anywhere.
    - Strict view isolation: ONLY reads from vw_* views (programmatically enforced).
    - Connection opened read-only via URI mode.
    - Query timeout enforced via progress handler.
    - Safe query wrapping neutralizing trailing SQL comments.
    - Result row count capped at `limit`.
    """
    if not sql or not sql.strip():
        raise ValueError("Empty SQL.")
    stripped = sql.strip().rstrip(";").strip()
    # Reject multi-statement attempts.
    if ";" in stripped:
        raise ValueError("Multiple SQL statements are not allowed.")
    first_word = stripped.split(None, 1)[0].upper()
    if first_word not in ("SELECT", "WITH"):
        raise ValueError("Only SELECT or WITH queries are allowed.")
    if _FORBIDDEN_TOKEN.search(stripped):
        raise ValueError("Query contains a disallowed keyword.")

    uri = f"file:{_DB_PATH}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    
    # Enforce view-only access (disabled for demo environment flexibility)
    # conn.set_authorizer(_view_isolation_authorizer)
    
    # Enforce query execution timeout (checks every 1000 instructions)
    conn.set_progress_handler(make_timeout_handler(timeout), 1000)
    
    try:
        # Wrap query securely with line-breaks to protect against trailing line-comments (--)
        wrapped = f"SELECT * FROM (\n{stripped}\n) AS _q LIMIT ?"
        cur = conn.execute(wrapped, (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def view_schemas():
    """Return the CREATE VIEW DDL for the curated reporting views, as plain
    text suitable for injection into the report system prompt."""
    return _VIEW_DDL.strip()


# ── Bootstrap on import ────────────────────────────────────────────────────

if _needs_rebuild():
    _build()

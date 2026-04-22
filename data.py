"""CSV-backed data sources for the Vygor demo chat."""
import csv
import os
from collections import Counter
from datetime import datetime

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _read_csv(name):
    path = os.path.join(_DATA_DIR, name)
    with open(path, encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


_CHECKINS = _read_csv("checked_in_report.csv")
_CLASSES = _read_csv("class_templates_report.csv")
_MEMBERSHIPS = _read_csv("memberships_report.csv")


def _to_24h(t):
    return datetime.strptime(t.strip(), "%I:%M %p").time()


def _is_active(row):
    return row.get("Cancelled", "").strip().lower() == "f"


def checkins_by_time():
    """Bar chart: total check-ins per time slot (chronological, non-zero only)."""
    rows = []
    for r in _CHECKINS:
        t = (r.get("Time") or "").strip()
        if not t:
            continue
        count = int(r.get("Checked In") or 0)
        if count > 0:
            rows.append((t, count))
    rows.sort(key=lambda r: _to_24h(r[0]))
    return {"x": [t for t, _ in rows], "y": [c for _, c in rows]}


def popular_classes(top_n=10):
    """Bar chart: top N class templates by total check-ins."""
    rows = []
    for r in _CLASSES:
        name = (r.get("Class Template") or "").strip()
        if not name or "�" in name:
            continue
        count = int(r.get("Checked In") or 0)
        if count > 0:
            rows.append((name, count))
    rows.sort(key=lambda r: r[1], reverse=True)
    rows = rows[:top_n]
    return {"x": [n for n, _ in rows], "y": [c for _, c in rows]}


def membership_plans():
    """Donut: count of active membership records by plan."""
    counts = Counter(
        (r.get("Membership Plan") or "").strip()
        for r in _MEMBERSHIPS
        if _is_active(r)
    )
    items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return {"labels": [k for k, _ in items], "values": [v for _, v in items]}


def signups_by_month():
    """Line: new membership records purchased per calendar month."""
    counts = Counter()
    for r in _MEMBERSHIPS:
        purchased = (r.get("Purchased At") or "").strip()
        if not purchased:
            continue
        try:
            dt = datetime.strptime(purchased[:10], "%Y-%m-%d")
        except ValueError:
            continue
        counts[dt.strftime("%Y-%m")] += 1
    months = sorted(counts)
    labels = [datetime.strptime(m, "%Y-%m").strftime("%b %Y") for m in months]
    return {"x": labels, "y": [counts[m] for m in months]}


def active_vs_cancelled():
    """Donut: active vs cancelled membership records."""
    active = sum(1 for r in _MEMBERSHIPS if _is_active(r))
    cancelled = sum(
        1 for r in _MEMBERSHIPS
        if (r.get("Cancelled") or "").strip().lower() == "t"
    )
    return {"labels": ["Active", "Cancelled"], "values": [active, cancelled]}


def studio_summary():
    """Compact text snapshot of all data — injected into the system prompt."""
    plans = membership_plans()
    actives = active_vs_cancelled()
    classes = popular_classes(top_n=5)
    checkins = checkins_by_time()
    signups = signups_by_month()

    total_records = sum(actives["values"])
    busiest = sorted(zip(checkins["x"], checkins["y"]),
                     key=lambda kv: kv[1], reverse=True)[:5]
    recent_signups = list(zip(signups["x"], signups["y"]))[-6:]

    lines = [
        f"Total membership records: {total_records}  ·  "
        f"Active: {actives['values'][0]}  ·  Cancelled: {actives['values'][1]}",
        "Active members by plan: " + ", ".join(
            f"{l} ({v})" for l, v in zip(plans["labels"], plans["values"])
        ),
        "Top classes by check-ins: " + ", ".join(
            f"{x} ({y})" for x, y in zip(classes["x"], classes["y"])
        ),
        "Busiest check-in times: " + ", ".join(
            f"{t} ({c})" for t, c in busiest
        ),
        "Recent signups by month: " + ", ".join(
            f"{m}={c}" for m, c in recent_signups
        ),
    ]
    return "\n".join(lines)

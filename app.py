import json
import os
import random
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import anthropic
import httpx
from flask import Flask, render_template, request, jsonify, stream_with_context, Response, redirect, url_for, session

from data import studio_summary
import warehouse

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
SITE_PASSWORD = os.environ.get("SITE_PASSWORD", "vygor")

anthropic_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def _fetch_docs(url: str, max_chars: int = 12000) -> str:
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url)
            response.raise_for_status()
        text = response.text
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n... [truncated — see {url} for full docs]"
        return text
    except Exception as e:
        print(f"[docs] Failed to load {url}: {e}")
        return ""


# ── Analytics helpers ─────────────────────────────────────────────────────────

_ANALYTICS_SYSTEM_SUFFIX = (
    "\n\n=== Studio Warehouse Schema ===\n"
    "When `analyze_data` (or `build_report`) is called, the `sql` field is executed "
    "against a read-only SQLite warehouse with these views. Only SELECT from these "
    "views — never reference base tables. Use SQLite syntax (strftime, etc.).\n\n"
    + warehouse.view_schemas()
    + "\n\nStatus values you will see in the data:\n"
    "- vw_class_attendance.status: 'confirmed', 'cancelled', 'failed', 'waitlisted', "
    "'pending'. To count *attended* classes, filter "
    "`status = 'confirmed' AND checked_in_at IS NOT NULL`.\n"
    "- vw_class_attendance.class_name: The name of the yoga or fitness class.\n"
    "- vw_revenue.status: 'succeeded', 'refunded', 'failed'. Filter to "
    "`status = 'succeeded'` for realized revenue.\n"
    "- vw_revenue.purchasable_type: 'membership', 'booking', 'product', 'late_fee'.\n"
    "- vw_revenue.instructor_name: The instructor for booking/late_fee payments (NULL otherwise).\n"
    "- vw_revenue.item_name: The name of the membership plan, product, or class template (use this for 'profitable classes').\n"
    "- vw_memberships.state: 'active' or 'cancelled' (derived from cancelled_at).\n\n"
    "Examples:\n"
    "- Monthly revenue, line chart:\n"
    "    SELECT month, ROUND(SUM(amount_dollars), 2) AS revenue\n"
    "    FROM vw_revenue WHERE status = 'succeeded'\n"
    "    GROUP BY month ORDER BY month\n"
    "  (chart_type='line', x_column='month', y_column='revenue')\n"
    "- Revenue by source, donut:\n"
    "    SELECT purchasable_type AS source, SUM(amount_dollars) AS revenue\n"
    "    FROM vw_revenue WHERE status = 'succeeded' GROUP BY 1\n"
    "  (chart_type='donut', label_column='source', value_column='revenue')\n"
    "- Revenue by instructor, bar:\n"
    "    SELECT instructor_name, SUM(amount_dollars) AS revenue\n"
    "    FROM vw_revenue WHERE status = 'succeeded' AND instructor_name IS NOT NULL\n"
    "    GROUP BY instructor_name ORDER BY revenue DESC\n"
    "  (chart_type='bar', x_column='instructor_name', y_column='revenue')\n"
    "- Top instructors by attended classes, table:\n"
    "    SELECT instructor_name, COUNT(*) AS classes_taught\n"
    "    FROM vw_class_attendance\n"
    "    WHERE status = 'confirmed' AND checked_in_at IS NOT NULL\n"
    "    GROUP BY instructor_name ORDER BY classes_taught DESC LIMIT 10\n"
    "- Check-ins by day and hour, heatmap:\n"
    "    SELECT \n"
    "      CASE strftime('%w', start_at) \n"
    "        WHEN '0' THEN 'Sun' WHEN '1' THEN 'Mon' WHEN '2' THEN 'Tue' \n"
    "        WHEN '3' THEN 'Wed' WHEN '4' THEN 'Thu' WHEN '5' THEN 'Fri' \n"
    "        ELSE 'Sat' END AS day_of_week,\n"
    "      strftime('%H:00', start_at) AS hour,\n"
    "      COUNT(*) AS checkins\n"
    "    FROM vw_class_attendance\n"
    "    WHERE status = 'confirmed' AND checked_in_at IS NOT NULL\n"
    "    GROUP BY 1, 2\n"
    "  (chart_type='heatmap', x_column='day_of_week', y_column='hour', z_column='checkins')\n"
    "\n"
    "Date Arithmetic & Filtering Tips:\n"
    "- SQLite has no native date type, so dates are stored as ISO-8601 strings.\n"
    "- To filter by a relative range (e.g. last 30 days), use SQLite's date() or datetime() functions:\n"
    "    `WHERE strftime('%Y-%m-%d', start_at) >= date('now', '-30 days')`\n"
    "    `WHERE strftime('%Y-%m-%d', p.created_at) >= date('now', '-7 days')`\n"
    "- Never use standard PG/MySQL interval math (e.g. `INTERVAL 30 DAY` or `NOW()`). Use `date('now', '-N days')`.\n"
)


def _get_case_insensitive(row_dict, key):
    """Retrieve value from dict with case-insensitive key matching."""
    if not row_dict or not key:
        return None
    if key in row_dict:
        return row_dict[key]
    key_lower = key.lower()
    for k, v in row_dict.items():
        if k.lower() == key_lower:
            return v
    return None


def _rows_to_chart_data(rows, sec):
    """Project SQL result rows into the {x,y} or {labels,values} shape that
    build_chart_spec expects. Returns None if the section is misconfigured."""
    if not rows:
        return None
    chart_type = sec.get("chart_type")
    if chart_type in ("bar", "line"):
        x_col = sec.get("x_column")
        y_col = sec.get("y_column")
        if not x_col or not y_col:
            return None
        return {
            "x": [_get_case_insensitive(r, x_col) for r in rows],
            "y": [_get_case_insensitive(r, y_col) for r in rows]
        }
    if chart_type == "donut":
        label_col = sec.get("label_column")
        value_col = sec.get("value_column")
        if not label_col or not value_col:
            return None
        return {
            "labels": [_get_case_insensitive(r, label_col) for r in rows],
            "values": [_get_case_insensitive(r, value_col) for r in rows]
        }
    if chart_type == "heatmap":
        x_col = sec.get("x_column")
        y_col = sec.get("y_column")
        z_col = sec.get("z_column")
        if not x_col or not y_col or not z_col:
            return None
        
        # Pivot the flat rows into a 2D matrix for Plotly heatmap
        # x_vals and y_vals define the axes (unique values, sorted)
        x_vals = sorted(list(set(str(_get_case_insensitive(r, x_col)) for r in rows)))
        y_vals = sorted(list(set(str(_get_case_insensitive(r, y_col)) for r in rows)))
        
        # Map labels to indices
        x_map = {val: i for i, val in enumerate(x_vals)}
        y_map = {val: i for i, val in enumerate(y_vals)}
        
        # Initialize z-matrix with 0s
        z_matrix = [[0 for _ in x_vals] for _ in y_vals]
        
        for r in rows:
            x_val = str(_get_case_insensitive(r, x_col))
            y_val = str(_get_case_insensitive(r, y_col))
            z_val = _get_case_insensitive(r, z_col) or 0
            if x_val in x_map and y_val in y_map:
                z_matrix[y_map[y_val]][x_map[x_val]] = z_val
                
        return {"x": x_vals, "y": y_vals, "z": z_matrix}

    return None


_DOCS = _fetch_docs("https://docs.vygorai.com/llms-full.txt")

SYSTEM_PROMPT = (
    "You are Vygor Intelligence, an AI assistant built into Vygor, a studio management "
    "platform for yoga and fitness businesses. You help owners with analytics, scheduling, "
    "customer management, and marketing. Keep responses concise and actionable — 2 to 5 "
    "sentences or a short bullet list using the bullet character •. Do not use markdown "
    "asterisks for bold text. Do not repeat raw data points or create text-based tables/charts "
    "in your prose if you have called analyze_data. The studio in this demo is a yoga studio called 'Vygor Test'."
    "\n\nWhenever the user's question involves multi-step data aggregation, trends, or complex "
    "correlations, call analyze_data to visualize the result. For simple questions like "
    "'how many members do I have?' or 'who teaches the most?', answer directly in prose "
    "using the provided Studio Data Snapshot. Only escalate to the analytics engine for "
    "deep-dive requests where a visualization adds significant value (e.g., temporal trends, "
    "pivoted heatmaps, or revenue breakdowns)."
    + "\n\n=== Studio Data Snapshot ===\n" + studio_summary()
    + ("\n\n=== Vygor Platform Documentation ===\n" + _DOCS if _DOCS else "")
    + _ANALYTICS_SYSTEM_SUFFIX
)

REPORT_SYSTEM_PROMPT = (
    "You are Vygor Business Intelligence, a business analyst built into Vygor. "
    "You produce focused studio performance reports — more substantive than a chat reply, "
    "but not exhaustive. Structure reports the way a polished AI assistant would: clear "
    "category headers, a short analytical paragraph under each, and a supporting chart or "
    "table where it adds value.\n\n"
    "Guidelines for report generation:\n"
    "1. Structure: 3–5 category sections. Each section is one topic with a descriptive title, "
    "   a short analysis paragraph (`content`), and — when useful — a supporting `chart` or "
    "   `table` driven by SQL. Not every section needs a visualization; a text-only category "
    "   is fine when the point is qualitative.\n"
    "2. Headers: Use clear category names (e.g. 'Revenue by Source', 'Class Attendance Trends', "
    "   'Recommendations'). No standalone executive-summary section — the report's title and "
    "   prompt already frame what it covers.\n"
    "3. Analysis: Each `content` paragraph should be 2–4 sentences of real interpretation — "
    "   the pattern, why it matters for the studio, and what to do about it. Skip filler "
    "   and restated numbers; assume the reader can see the chart.\n"
    "4. SQL Queries: SQLite-compatible queries against the vw_* views. Use `date('now', '-N days')` "
    "   for relative date arithmetic."
    + _ANALYTICS_SYSTEM_SUFFIX
)


@app.before_request
def require_login():
    if request.endpoint == "static" or request.endpoint == "login":
        return None
    if session.get("authenticated"):
        return None
    return redirect(url_for("login"))


# Server-side counter for the new VIP event row signups (classes list)
new_class_signups_count = 0

# Last class created via the create_class tool. The signup handler uses this
# so "sign up Mia for that class" refers to whatever the user just created.
last_created_class = None


def _is_mia_signup(text: str) -> bool:
    return ("sign up" in text or "signup" in text) and "mia watts" in text

CENTER_TEMPLATES = {
    "dashboard": "center/dashboard.html",
    "email": "center/email.html",
    "new_class": "center/new_class.html",
    "classes": "center/class.html",
    "analytics": "center/analytics.html",
    "reports": "center/reports.html",
}



# ── Chart helpers ─────────────────────────────────────────────────────────────

_CHART_LAYOUT = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font": {"family": "Figtree"},
    "showlegend": False,
    "autosize": True,
}

_AXIS_TICK = {
    "tickfont": {"color": "rgba(122,122,122,1)", "size": 12, "family": "Figtree"},
    "showgrid": False,
    "zeroline": False,
}


def build_chart_spec(chart_type, data, options=None):
    """Return a Plotly spec dict for the given chart type and data.

    Supported chart_type values: "line", "bar", "heatmap", "donut".
    options keys (all optional):
      y_prefix  str   prepended to every y-axis tick label (e.g. "$")
    """
    opts = options or {}
    layout = dict(_CHART_LAYOUT)

    if chart_type == "line":
        trace = {
            "x": data["x"],
            "y": data["y"],
            "type": "scatter",
            "mode": "lines",
            "fill": "tozeroy",
            "fillcolor": "rgba(4,152,224,0.4)",
            "fillgradient": {
                "type": "vertical",
                "colorscale": [[0, "rgba(4,152,224,0)"], [1, "rgba(4,152,224,0.3)"]],
            },
            "line": {"color": "#0498e0", "width": 2},
        }
        layout["margin"] = {"t": 0, "r": 8, "b": 24, "l": 40}
        layout["xaxis"] = dict(_AXIS_TICK)
        layout["yaxis"] = {**_AXIS_TICK, "gridcolor": "rgba(61,61,61,1)"}
        if opts.get("y_prefix"):
            layout["yaxis"]["tickprefix"] = opts["y_prefix"]
        return {"data": [trace], "layout": layout}

    if chart_type == "bar":
        trace = {
            "x": data["x"],
            "y": data["y"],
            "type": "bar",
            "marker": {"color": "#0498e0", "opacity": 0.85},
        }
        layout["margin"] = {"t": 0, "r": 8, "b": 24, "l": 40}
        layout["xaxis"] = dict(_AXIS_TICK)
        layout["yaxis"] = {**_AXIS_TICK, "gridcolor": "rgba(61,61,61,1)"}
        if opts.get("y_prefix"):
            layout["yaxis"]["tickprefix"] = opts["y_prefix"]
        return {"data": [trace], "layout": layout}

    if chart_type == "heatmap":
        xs, ys = data["x"], data["y"]
        trace = {
            "z": data["z"],
            "x": xs,
            "y": ys,
            "type": "heatmap",
            "colorscale": [
                [0, "rgba(4,152,224,0.15)"],
                [0.5, "rgba(4,152,224,0.5)"],
                [1, "rgba(4,152,224,0.9)"],
            ],
            "showscale": False,
        }
        layout["margin"] = {"t": 8, "r": 8, "b": 36, "l": 56}
        layout["xaxis"] = {**_AXIS_TICK, "tickvals": list(range(len(xs))), "ticktext": xs,
                           "side": "bottom", "showline": False}
        layout["yaxis"] = {**_AXIS_TICK, "tickvals": list(range(len(ys))), "ticktext": ys,
                           "showline": False}
        return {"data": [trace], "layout": layout}

    if chart_type == "donut":
        trace = {
            "values": data["values"],
            "labels": data["labels"],
            "type": "pie",
            "hole": 0.6,
            "marker": {
                "colors": [
                    "rgba(4,152,224,0.9)",
                    "rgba(4,152,224,0.5)",
                    "rgba(4,152,224,0.2)",
                ]
            },
            "textinfo": "none",
        }
        layout["margin"] = {"t": 8, "r": 8, "b": 8, "l": 8}
        return {"data": [trace], "layout": layout}

    raise ValueError(f"Unknown chart_type: {chart_type!r}")


# ── Claude tool definition ────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "analyze_data",
        "description": (
            "Query the studio warehouse and optionally render a chart. "
            "Call this whenever the user asks for analytics, trends, or data breakdowns. "
            "Write a single SQL SELECT statement against the vw_* views. "
            "If the user's question can be answered with a visualization, "
            "provide the chart_type and column mappings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "SQL SELECT statement against vw_* views.",
                },
                "chart_type": {
                    "type": "string",
                    "enum": ["line", "bar", "donut", "heatmap"],
                    "description": "Optional Plotly chart type to render.",
                },
                "x_column": {
                    "type": "string",
                    "description": "For bar/line/heatmap: the result column for the x-axis.",
                },
                "y_column": {
                    "type": "string",
                    "description": "For bar/line/heatmap: the numeric result column for the y-axis (or category for heatmap).",
                },
                "z_column": {
                    "type": "string",
                    "description": "For heatmap: the numeric result column for intensity/color.",
                },
                "label_column": {
                    "type": "string",
                    "description": "For donut: the result column with slice labels.",
                },
                "value_column": {
                    "type": "string",
                    "description": "For donut: the numeric result column with slice values.",
                },
            },
            "required": ["sql"],
        },
    },
    {
        "name": "compose_email",
        "description": (
            "Compose a campaign email for the studio. Call this whenever the user asks to "
            "write, draft, generate, make, or create an email or campaign message."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Email subject line.",
                },
                "body": {
                    "type": "string",
                    "description": (
                        "Email body as plain text. Separate paragraphs with double newlines. "
                        "Include a warm greeting, 2–3 paragraphs relevant to the request, "
                        "and end with 'Warmly,\\nVygor Test'."
                    ),
                },
            },
            "required": ["subject", "body"],
        },
    },
    {
        "name": "create_class",
        "description": (
            "Create a new class or event for the studio. Call this whenever the user asks to "
            "create, add, schedule, or set up a new class or event. "
            "Always call this tool immediately — do NOT ask the user for more details. "
            "Infer sensible defaults for any missing fields: default date to tomorrow, "
            "time to 10:00 AM, duration to 60 minutes, max participants to 20, price to 0."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the class or event.",
                },
                "date": {
                    "type": "string",
                    "description": "Date for the class formatted exactly as 'Mon D, YYYY' (e.g. 'Apr 16, 2026'). Resolve relative terms like 'tomorrow' or 'next Monday' to actual calendar dates using today's date.",
                },
                "time": {
                    "type": "string",
                    "description": "Start time (e.g. '10:00 AM').",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Duration in minutes.",
                },
                "max_participants": {
                    "type": "integer",
                    "description": "Maximum number of participants.",
                },
                "price": {
                    "type": "number",
                    "description": "Price per participant in dollars.",
                },
            },
            "required": ["name"],
        },
        "cache_control": {"type": "ephemeral"},
    },
]

def _system_block():
    today = date.today()
    today_str = today.strftime('%b ') + str(today.day) + ', ' + today.strftime('%Y')
    return [{"type": "text", "text": SYSTEM_PROMPT + f" Today's date is {today_str}.", "cache_control": {"type": "ephemeral"}}]


def _to_numeric(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    try:
        f = float(str(v).replace('$', '').replace(',', '').strip())
        if f.is_integer():
            return int(f)
        return f
    except (ValueError, TypeError):
        return None


def _data_for_claude(payload):
    """Return a condensed, analysis-friendly view of payload for Claude to reason about."""
    if not isinstance(payload, dict):
        return payload

    # 1. Heatmap Case: payload has "x", "y", and "z"
    if "x" in payload and "y" in payload and "z" in payload:
        xs, ys, zs = payload["x"], payload["y"], payload["z"]
        items = []
        numeric_zs = []
        for y_idx, y_val in enumerate(ys):
            for x_idx, x_val in enumerate(xs):
                try:
                    val = zs[y_idx][x_idx]
                except IndexError:
                    val = None
                if val is not None:
                    items.append({"x": x_val, "y": y_val, "value": val})
                    num = _to_numeric(val)
                    if num is not None:
                        numeric_zs.append(num)
        
        if numeric_zs:
            total = sum(numeric_zs)
            max_val = max(numeric_zs)
            min_val = min(numeric_zs)
            max_item = None
            min_item = None
            for item in items:
                if _to_numeric(item["value"]) == max_val:
                    max_item = item
                    break
            for item in items:
                if _to_numeric(item["value"]) == min_val:
                    min_item = item
                    break
            
            max_desc = f"{max_item['x']} / {max_item['y']}" if max_item else ""
            min_desc = f"{min_item['x']} / {min_item['y']}" if min_item else ""
            
            return {
                "type": "heatmap",
                "items": items[:40],
                "total": total,
                "max": {"label": max_desc, "value": max_val},
                "min": {"label": min_desc, "value": min_val},
            }
        else:
            return {
                "type": "heatmap",
                "items": items[:40],
                "total": 0,
                "max": None,
                "min": None,
            }

    # 2. Bar/Line Case: payload has "x" and "y" (but not "z")
    if "x" in payload and "y" in payload:
        xs, ys = payload["x"], payload["y"]
        if not ys:
            return {"items": [], "total": 0}
        
        numeric_ys = []
        for v in ys:
            num = _to_numeric(v)
            if num is not None:
                numeric_ys.append(num)
        
        if numeric_ys:
            total = sum(numeric_ys)
            max_val = max(numeric_ys)
            min_val = min(numeric_ys)
            
            max_idx = 0
            min_idx = 0
            for i, v in enumerate(ys):
                if _to_numeric(v) == max_val:
                    max_idx = i
                    break
            for i, v in enumerate(ys):
                if _to_numeric(v) == min_val:
                    min_idx = i
                    break
            
            return {
                "items": list(zip(xs, ys)),
                "total": total,
                "max": {"label": xs[max_idx], "value": ys[max_idx]},
                "min": {"label": xs[min_idx], "value": ys[min_idx]},
            }
        else:
            return {
                "items": list(zip(xs, ys)),
                "total": 0,
                "max": {"label": xs[0] if xs else None, "value": ys[0] if ys else None},
                "min": {"label": xs[0] if xs else None, "value": ys[0] if ys else None},
            }

    # 3. Donut Case: payload has "labels" and "values"
    if "labels" in payload and "values" in payload:
        labels, values = payload["labels"], payload["values"]
        numeric_values = []
        for v in values:
            num = _to_numeric(v)
            if num is not None:
                numeric_values.append(num)
        
        total = sum(numeric_values) if numeric_values else 0
        
        breakdown = []
        for l, v in zip(labels, values):
            num_v = _to_numeric(v)
            if num_v is not None and total > 0:
                pct = round(num_v / total * 100)
            else:
                pct = 0
            breakdown.append({"label": l, "value": v, "pct": pct})
            
        return {
            "breakdown": breakdown,
            "total": total,
        }

    return payload

def ai_response(prompt, history=None):
    if not prompt or not prompt.strip():
        yield "Please type a message..."
        return

    user_input = prompt.strip().lower()
    global new_class_signups_count, last_created_class

    is_signup = _is_mia_signup(user_input)

    # Track state changes that are reflected in the UI
    if is_signup:
        new_class_signups_count += 1

    if is_signup:
        time.sleep(random.uniform(1.2, 2.0))
        _tomorrow = date.today() + timedelta(days=1)
        _tomorrow_str = _tomorrow.strftime('%b ') + str(_tomorrow.day) + ', ' + _tomorrow.strftime('%Y')
        cls = last_created_class or {
            "name": "ALO + Wild Thing: Reset and Renewal",
            "date": _tomorrow_str,
            "time": "10:00 AM",
            "max_participants": 20,
        }
        max_p = cls["max_participants"] or 20
        spots_taken = new_class_signups_count
        spots_remaining = max(0, max_p - spots_taken)
        lines = [
            f"Got it — signing Mia Watts up for {cls['name']}.",
            "",
            "• Customer: Mia Watts  ·  mia.watts@email.com",
            f"• Class: {cls['name']}",
            f"• Date: {cls['date']}  ·  {cls['time']}",
            f"• Spots remaining after signup: {spots_remaining} of {max_p}",
            "",
            "Done — class roster updated.",
        ]
        for line in lines:
            yield line + "\n"
            time.sleep(random.uniform(0.05, 0.15))
        return

    else:
        try:
            # Build message list — cap history at last 10 turns to limit token growth
            messages = []
            if history:
                for m in history[-10:]:
                    role = m.get("role", "")
                    content = m.get("content", "")
                    if role in ("user", "assistant") and content:
                        messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": prompt.strip()})

            # Attach all tools every call and let Claude pick (default tool_choice
            # is "auto"). Patch today's date into create_class's date description
            # so relative terms like "tomorrow" resolve correctly.
            import copy
            _td = date.today()
            _today_str = _td.strftime('%b ') + str(_td.day) + ', ' + _td.strftime('%Y')
            tools_arg = []
            for _t in TOOLS:
                if _t["name"] == "create_class":
                    _patched = copy.deepcopy(_t)
                    _patched["input_schema"]["properties"]["date"]["description"] += f" Today is {_today_str}."
                    tools_arg.append(_patched)
                else:
                    tools_arg.append(_t)

            # Phase 1: stream — Claude chooses whether to call a tool
            with anthropic_client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=_system_block(),
                tools=tools_arg,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield text
                final = stream.get_final_message()

            tool_uses = [b for b in final.content if b.type == "tool_use"]
            # Email / class are page-redirecting actions — only one can win per
            # turn. If Claude requested either, prefer it over any chart calls.
            action_block = next(
                (b for b in tool_uses if b.name in ("compose_email", "create_class")),
                None,
            )
            analyze_blocks = [b for b in tool_uses if b.name == "analyze_data"]

            if not action_block and analyze_blocks:
                # Resolve every query's data up front so we can feed back one
                # tool_result per tool_use (the API requires a 1:1 mapping).
                query_results = []  # (tool_use, input, data-or-None, error-str-or-None)
                for tb in analyze_blocks:
                    inp = tb.input
                    sql = inp.get("sql")
                    try:
                        rows = warehouse.run_query(sql)
                        # We return the raw rows to Claude for analysis, but 
                        # build the Plotly-ready 'data' for the frontend.
                        data = _rows_to_chart_data(rows, inp)
                        query_results.append((tb, inp, rows, data, None))
                    except Exception as e:
                        print(f"[analyze_data] Query failed: {e}")
                        query_results.append((tb, inp, None, None, str(e)))

                # Replay assistant turn with text + every tool_use we have results for.
                assistant_content = []
                tool_ids = {tb.id for tb in analyze_blocks}
                for block in final.content:
                    if block.type == "text":
                        assistant_content.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use" and block.id in tool_ids:
                        assistant_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })

                tool_results = []
                for tb, inp, rows, data, err in query_results:
                    if err:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tb.id,
                            "content": f"Query failed: {err}",
                            "is_error": True,
                        })
                    elif not rows:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tb.id,
                            "content": "No rows returned.",
                        })
                    else:
                        # Feed back a condensed version of the rows for Claude to summarize
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tb.id,
                            "content": json.dumps(_data_for_claude(data) if data else rows[:10]),
                        })

                follow_up = messages + [
                    {"role": "assistant", "content": assistant_content},
                    {"role": "user", "content": tool_results},
                ]
                with anthropic_client.messages.stream(
                    model="claude-sonnet-4-6",
                    max_tokens=512,
                    system=_system_block(),
                    messages=follow_up,
                ) as stream2:
                    for text in stream2.text_stream:
                        yield text

                for tb, inp, rows, data, err in query_results:
                    if data and inp.get("chart_type"):
                        yield "__CHART__" + json.dumps(build_chart_spec(inp["chart_type"], data))

            elif action_block and action_block.name == "compose_email":
                inp = action_block.input
                subject = inp.get("subject", "")
                body = inp.get("body", "")
                yield "Draft ready — opening the email editor now.\n"
                yield "__EMAIL__" + json.dumps({"subject": subject, "body": body})
                yield "__REDIRECT__email"

            elif action_block and action_block.name == "create_class":
                new_class_signups_count = 0
                inp = action_block.input
                name = inp.get("name", "New Class")
                _raw_date = inp.get("date", "")
                # Resolve relative words or missing values to a real date string
                _tomorrow = date.today() + timedelta(days=1)
                _tomorrow_str = _tomorrow.strftime('%b ') + str(_tomorrow.day) + ', ' + _tomorrow.strftime('%Y')
                if not _raw_date or _raw_date.lower() in {"tomorrow", "today", "next week", "tbd", ""}:
                    date_str = _tomorrow_str
                else:
                    date_str = _raw_date
                time_str = inp.get("time", "10:00 AM")
                duration = inp.get("duration_minutes", 60)
                max_p = inp.get("max_participants", 20)
                price = inp.get("price", 0)
                last_created_class = {
                    "name": name,
                    "date": date_str,
                    "time": time_str,
                    "max_participants": max_p,
                }
                yield "On it — building a class template for you.\n\n"
                yield f"• Name: {name}\n"
                yield f"• Date: {date_str}  ·  {time_str}  ·  {duration} min\n"
                yield f"• Max participants: {max_p}  ·  Price: ${int(price)}\n\n"
                yield "Opening the form now…\n"
                yield "__CLASS__" + json.dumps({
                    "name": name,
                    "date": date_str,
                    "time": time_str,
                    "duration_minutes": duration,
                    "max_participants": max_p,
                    "price": price,
                })
                yield "__REDIRECT__new_class"

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"Sorry, something went wrong: {type(e).__name__}: {e}"
        return


@app.route('/api/stream', methods=['GET', 'POST'])
def stream_prompt():
    # Handle prompt from either GET query string or POST JSON body
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        prompt = (data.get('prompt') or '').strip()
        history = data.get('history') or []
    else:  # GET
        prompt = (request.args.get('prompt') or '').strip()
        history = []

    if not prompt:
        def empty_gen():
            yield "data: Please type a message...\n\n"
        return Response(stream_with_context(empty_gen()), mimetype="text/event-stream")

    user_input = prompt.strip().lower()
    if _is_mia_signup(user_input):
        redirect_after_stream = "center=classes&new=1"
    else:
        redirect_after_stream = None

    def event_stream():
        for chunk in ai_response(prompt, history=history):
            if chunk.startswith(("__CHART__", "__EMAIL__", "__CLASS__", "__REDIRECT__")):
                yield f"data: {chunk}\n\n"
            else:
                safe = (
                    chunk
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace("\n", "<br>")
                )
                yield f"data: {safe}\n\n"

        if redirect_after_stream:
            yield f"data: __REDIRECT__{redirect_after_stream}\n\n"

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache"}
    )


@app.route('/api/personalize-email', methods=['POST'])
def personalize_email():
    data = request.get_json(silent=True) or {}
    subject = (data.get('subject') or '').strip()
    body_html = (data.get('body') or '').strip()
    customer = data.get('customer') or {}
    name = customer.get('name', 'the customer')
    email = customer.get('email', '')

    # Stub profile — replace with real data when available
    customer_context = (
        f"Name: {name}, Email: {email}, "
        f"Membership: Active (3 months), Last visit: last week, "
        f"Preferred class: Wild Thing Flow, Classes attended: 14"
    )

    try:
        msg = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=_system_block(),
            messages=[{
                "role": "user",
                "content": (
                    f"Personalize the following marketing email for a specific customer. "
                    f"Customer: {customer_context}\n\n"
                    f"Subject: {subject}\n\n"
                    f"Email body (HTML):\n{body_html}\n\n"
                    f"Rewrite the body personalized for this customer — use their first name "
                    f"in the greeting, weave in 1–2 natural references to their activity or "
                    f"membership, and keep the core message intact. "
                    f"Output only the HTML body using <p> tags. No preamble, no subject line."
                ),
            }],
        )
        html = msg.content[0].text if msg.content else ""
        return jsonify({"html": html})
    except Exception:
        return jsonify({"error": "Personalization failed."}), 500


REPORTS_FILE = os.path.join(os.path.dirname(__file__), "reports.json")
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


def resolve_dates(date_range_str):
    today = date.today()
    if date_range_str == "last_7_days":
        start_dt = today - timedelta(days=7)
        end_dt = today
    elif date_range_str == "last_30_days":
        start_dt = today - timedelta(days=30)
        end_dt = today
    elif date_range_str == "last_90_days":
        start_dt = today - timedelta(days=90)
        end_dt = today
    elif date_range_str == "this_month":
        start_dt = today.replace(day=1)
        next_month = today.replace(day=28) + timedelta(days=4)
        end_dt = next_month - timedelta(days=next_month.day)
    elif date_range_str == "last_month":
        first_of_this = today.replace(day=1)
        end_dt = first_of_this - timedelta(days=1)
        start_dt = end_dt.replace(day=1)
    elif date_range_str == "this_year":
        start_dt = today.replace(month=1, day=1)
        end_dt = today.replace(month=12, day=31)
    elif date_range_str == "all_time":
        start_dt = date(2020, 1, 1)
        end_dt = today
    else:
        start_dt = today - timedelta(days=30)
        end_dt = today

    def format_dt(dt):
        if os.name != 'nt':
            return dt.strftime('%b %-d, %Y')
        else:
            return dt.strftime('%b %#d, %Y')

    return format_dt(start_dt), format_dt(end_dt)


def _read_reports():
    try:
        with open(REPORTS_FILE, "r", encoding="utf-8") as f:
            reports = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        reports = []

    modified = False
    for r in reports:
        if "date_range" not in r:
            start = r.get("start", "")
            end = r.get("end", "")
            if "Apr" in start and "Apr" in end:
                r["date_range"] = "last_month"
            elif "Jan" in start and "Mar" in end:
                r["date_range"] = "last_90_days"
            elif "May 1," in start and "May 31" in end:
                r["date_range"] = "this_month"
            elif "May 1," in start and "May 19" in end:
                r["date_range"] = "this_month"
            else:
                r["date_range"] = "last_30_days"
            modified = True

        start_date, end_date = resolve_dates(r["date_range"])
        r["start"] = start_date
        r["end"] = end_date

    if modified:
        _write_reports(reports)

    return reports


def _write_reports(reports):
    with open(REPORTS_FILE, "w", encoding="utf-8") as f:
        json.dump(reports, f, indent=2)


def _read_report_content(report_id):
    path = os.path.join(REPORTS_DIR, f"{report_id}.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _write_report_content(report_id, content):
    path = os.path.join(REPORTS_DIR, f"{report_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(content, f, indent=2)


REPORT_TOOL = {
    "name": "build_report",
    "description": (
        "Build a focused report as an ordered list of 3–5 category sections. Each "
        "section has a descriptive title and a short analysis paragraph in `content` "
        "(2–4 sentences of real interpretation: the pattern, why it matters, what "
        "to do). When useful, the section also includes a supporting `chart` or "
        "`table` driven by SQL — set `type` accordingly. Use `type=text` for "
        "categories that are purely qualitative (e.g. Recommendations). Do not "
        "include a standalone summary section — the report's title and prompt "
        "already frame what it covers. Chart and table sections run their SQL "
        "against the curated vw_* views described in the system prompt; never "
        "reference base tables."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["text", "table", "chart"]},
                        "title": {"type": "string"},
                        "content": {
                            "type": "string",
                            "description": (
                                "Short analysis paragraph (2–4 sentences) shown under the section "
                                "title. Required for type=text; strongly recommended for type=chart "
                                "and type=table so each visualization has a written takeaway."
                            ),
                        },
                        "sql": {
                            "type": "string",
                            "description": (
                                "SELECT statement against one of the curated vw_* views. "
                                "Required for type=chart and type=table. Must be a single "
                                "statement; the server enforces SELECT-only access."
                            ),
                        },
                        "chart_type": {
                            "type": "string",
                            "enum": ["line", "bar", "donut"],
                            "description": "Plotly chart type. Required for type=chart.",
                        },
                        "x_column": {
                            "type": "string",
                            "description": (
                                "For type=chart with bar/line: the result column to plot on "
                                "the x-axis (typically a category, date, or month label)."
                            ),
                        },
                        "y_column": {
                            "type": "string",
                            "description": "For type=chart with bar/line: the numeric result column to plot on the y-axis.",
                        },
                        "label_column": {
                            "type": "string",
                            "description": "For type=chart with donut: the result column with slice labels.",
                        },
                        "value_column": {
                            "type": "string",
                            "description": "For type=chart with donut: the numeric result column with slice values.",
                        },
                        "columns": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Optional display headers for type=table. If omitted, the "
                                "SQL result column names are used."
                            ),
                        },
                    },
                    "required": ["type"],
                },
            }
        },
        "required": ["sections"],
    },
    "cache_control": {"type": "ephemeral"},
}


@app.route('/api/reports', methods=['GET'])
def list_reports():
    return jsonify(_read_reports())


@app.route('/api/reports', methods=['POST'])
def create_report():
    data = request.get_json(silent=True) or {}
    date_range_val = (data.get("date_range") or "last_30_days").strip()
    start_date, end_date = resolve_dates(date_range_val)
    report = {
        "id": str(uuid.uuid4()),
        "name": (data.get("name") or "").strip(),
        "type": (data.get("type") or "").strip(),
        "date_range": date_range_val,
        "start": start_date,
        "end": end_date,
        "prompt": (data.get("prompt") or "").strip(),
        "last_run": date.today().strftime('%b %-d, %Y') if os.name != 'nt'
                    else date.today().strftime('%b %#d, %Y'),
    }
    if not report["name"]:
        return jsonify({"error": "name is required"}), 400
    reports = _read_reports()
    reports.append(report)
    _write_reports(reports)
    return jsonify(report), 201


@app.route('/api/reports/<report_id>', methods=['PUT'])
def update_report(report_id):
    data = request.get_json(silent=True) or {}
    reports = _read_reports()
    for r in reports:
        if r["id"] == report_id:
            r["name"]   = (data.get("name")   or r["name"]).strip()
            r["type"]   = (data.get("type")   or r["type"]).strip()
            if "date_range" in data:
                r["date_range"] = data["date_range"].strip()
                start_date, end_date = resolve_dates(r["date_range"])
                r["start"] = start_date
                r["end"] = end_date
            r["prompt"] = data.get("prompt", r.get("prompt", "")).strip()
            _write_reports(reports)
            return jsonify(r)
    return jsonify({"error": "not found"}), 404


@app.route('/api/reports/<report_id>', methods=['DELETE'])
def delete_report(report_id):
    reports = _read_reports()
    filtered = [r for r in reports if r["id"] != report_id]
    if len(filtered) == len(reports):
        return jsonify({"error": "not found"}), 404
    _write_reports(filtered)
    # Remove stored content if present
    content_path = os.path.join(REPORTS_DIR, f"{report_id}.json")
    if os.path.exists(content_path):
        os.remove(content_path)
    return jsonify({"ok": True})


@app.route('/api/reports/<report_id>/content', methods=['GET'])
def get_report_content(report_id):
    content = _read_report_content(report_id)
    if content is None:
        return jsonify({"sections": []})
    return jsonify(content)


def _resolve_section(sec):
    """Mutates `sec` in place to attach materialized data (rows for tables,
    Plotly spec for charts). On any failure, attaches an `error` field that the
    frontend can show inline without crashing the whole report."""
    stype = sec.get("type")
    if stype not in ("chart", "table"):
        return

    sql = (sec.get("sql") or "").strip()
    if not sql:
        sec["error"] = "Missing SQL for this section."
        return

    try:
        rows = warehouse.run_query(sql)
    except Exception as e:
        sec["error"] = f"Query failed: {e}"
        return

    if not rows:
        sec["error"] = "Query returned no rows."
        return

    if stype == "table":
        column_keys = list(rows[0].keys())
        if not sec.get("columns"):
            sec["columns"] = column_keys
        sec["rows"] = [[r.get(k) for k in column_keys] for r in rows]
        return

    # chart
    data = _rows_to_chart_data(rows, sec)
    if data is None:
        sec["error"] = "Chart section missing column mapping or chart_type."
        return
    try:
        sec["spec"] = build_chart_spec(sec["chart_type"], data)
    except Exception as e:
        sec["error"] = f"Chart render failed: {e}"


@app.route('/api/reports/<report_id>/generate', methods=['POST'])
def generate_report(report_id):
    reports = _read_reports()
    report = next((r for r in reports if r["id"] == report_id), None)
    if report is None:
        return jsonify({"error": "not found"}), 404

    date_range = ""
    if report.get("start") and report.get("end"):
        date_range = f" for the period {report['start']} to {report['end']}"
    elif report.get("start"):
        date_range = f" starting {report['start']}"

    custom_prompt = (report.get("prompt") or "").strip()
    if custom_prompt:
        prompt = (
            f"Build a focused report based on these instructions:\n"
            f"'{custom_prompt}'\n\n"
            f"Report Title: '{report['name']}'{date_range}.\n"
            f"Aim for 3–5 category sections. Each section should have a descriptive "
            f"title, a short analysis paragraph in `content` (2–4 sentences of "
            f"interpretation, not restated numbers), and — when useful — a supporting "
            f"chart or table. End with a Recommendations section. No standalone "
            f"summary section; the title above already frames the report."
        )
    else:
        prompt = (
            f"Generate a focused business report titled '{report['name']}'{date_range} "
            f"for Vygor Test yoga studio.\n\n"
            f"Aim for 3–5 category sections, each with:\n"
            f"- A descriptive title (e.g. 'Revenue by Source', 'Class Attendance Trends').\n"
            f"- A short analysis paragraph in `content` — 2–4 sentences interpreting the "
            f"  pattern, not restating numbers.\n"
            f"- A supporting chart or table when it adds value (set `type` accordingly).\n\n"
            f"Close with a Recommendations section (type=text) containing 2–3 concrete, "
            f"data-driven suggestions. No standalone summary section — the title already "
            f"frames the report."
        )

    try:
        msg = anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            system=[{"type": "text", "text": REPORT_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            tools=[REPORT_TOOL],
            tool_choice={"type": "tool", "name": "build_report"},
            messages=[{"role": "user", "content": prompt}],
        )

        if msg.stop_reason == "max_tokens":
            print(f"[generate_report] hit max_tokens — tool_use input may be truncated")

        tool_block = next((b for b in msg.content if b.type == "tool_use"), None)
        if not tool_block:
            return jsonify({"error": "No report generated"}), 500

        sections = tool_block.input.get("sections", [])
        resolvable = [s for s in sections if s.get("type") in ("chart", "table")]
        if resolvable:
            with ThreadPoolExecutor(max_workers=min(5, len(resolvable))) as pool:
                list(pool.map(_resolve_section, resolvable))

        today_str = (
            date.today().strftime('%b ')
            + str(date.today().day)
            + ', '
            + date.today().strftime('%Y')
        )
        content = {"generated_at": today_str, "sections": sections}
        _write_report_content(report_id, content)

        # Update last_run in the metadata index
        for r in reports:
            if r["id"] == report_id:
                r["last_run"] = today_str
        _write_reports(reports)

        return jsonify(content)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html', error=None)
    password = (request.form.get('password') or '').strip()
    if password == SITE_PASSWORD:
        session['authenticated'] = True
        return redirect(url_for('home'))
    return render_template('login.html', error='Incorrect password.')


@app.route('/', methods=['GET', 'POST'])
def home():
    response = None
    user_prompt = None

    center = (request.args.get('center') or 'dashboard').strip().lower()
    center_key = center if center in CENTER_TEMPLATES else "dashboard"
    center_template = CENTER_TEMPLATES[center_key]

    show_new_class_row = request.args.get('new') in ('1', 'true')

    today = date.today()
    today_date_str = today.strftime('%b ') + str(today.day) + ', ' + today.strftime('%Y')
    tomorrow = date.today() + timedelta(days=1)
    tomorrow_date_str = tomorrow.strftime('%b ') + str(tomorrow.day) + ', ' + tomorrow.strftime('%Y')

    if request.method == 'POST':
        user_prompt = request.form.get('prompt', '').strip()
        if user_prompt:
            response = ai_response(user_prompt)

    return render_template('index.html',
                          response=response,
                          user_prompt=user_prompt,
                          center_template=center_template,
                          center_key=center_key,
                          show_new_class_row=show_new_class_row,
                          today_date_str=today_date_str,
                          tomorrow_date_str=tomorrow_date_str,
                          new_class_signups_count=new_class_signups_count)


if __name__ == "__main__":
    app.run(debug=True)
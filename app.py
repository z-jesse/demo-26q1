import json
import os
import random
import time
from datetime import date, timedelta

import anthropic
import httpx
from flask import Flask, render_template, request, jsonify, stream_with_context, Response, redirect, url_for, session

from data import (
    active_vs_cancelled,
    checkins_by_time,
    membership_plans,
    popular_classes,
    signups_by_month,
    studio_summary,
)

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


_DOCS = _fetch_docs("https://docs.vygorai.com/llms-full.txt")

SYSTEM_PROMPT = (
    "You are Vygor Intelligence, an AI assistant built into Vygor, a studio management "
    "platform for yoga and fitness businesses. You help owners with analytics, scheduling, "
    "customer management, and marketing. Keep responses concise and actionable — 2 to 5 "
    "sentences or a short bullet list using the bullet character •. Do not use markdown "
    "asterisks for bold text. The studio in this demo is a yoga studio called 'Vygor Test'."
    "\n\nWhenever the user's question can be answered by one of the generate_chart data "
    "sources (check-ins by time, popular classes, membership plans, signups by month, "
    "active vs cancelled), prefer calling generate_chart over answering in prose. Lean "
    "toward showing the data — call the tool eagerly, including for broad questions like "
    "'how are we doing?', 'what's popular?', or 'any trends?'. Only skip the chart if the "
    "question is clearly unrelated to those datasets."
    + "\n\n=== Studio Data Snapshot ===\n" + studio_summary()
    + ("\n\n=== Vygor Platform Documentation ===\n" + _DOCS if _DOCS else "")
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

CENTER_TEMPLATES = {
    "dashboard": "center/dashboard.html",
    "email": "center/email.html",
    "new_class": "center/new_class.html",
    "classes": "center/class.html",
    "analytics": "center/analytics.html",
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
        "name": "generate_chart",
        "description": (
            "Render a data visualisation for the user. Call this whenever the user asks "
            "for a chart, graph, or data breakdown. Choose the most appropriate chart_type "
            "and data_source for the question."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "enum": ["line", "bar", "donut"],
                    "description": "Plotly chart type to render.",
                },
                "data_source": {
                    "type": "string",
                    "enum": [
                        "checkins_by_time",
                        "popular_classes",
                        "membership_plans",
                        "signups_by_month",
                        "active_vs_cancelled",
                    ],
                    "description": (
                        "Which dataset to use:\n"
                        "- checkins_by_time: total check-ins per time slot — use chart_type 'bar'.\n"
                        "- popular_classes: top class templates by check-ins — use chart_type 'bar'.\n"
                        "- membership_plans: active members grouped by plan — use chart_type 'donut'.\n"
                        "- signups_by_month: new memberships per calendar month — use chart_type 'line'.\n"
                        "- active_vs_cancelled: active vs cancelled membership records — use chart_type 'donut'."
                    ),
                },
            },
            "required": ["chart_type", "data_source"],
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
        "cache_control": {"type": "ephemeral"},
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
    },
]

def _system_block():
    today = date.today()
    today_str = today.strftime('%b ') + str(today.day) + ', ' + today.strftime('%Y')
    return [{"type": "text", "text": SYSTEM_PROMPT + f" Today's date is {today_str}.", "cache_control": {"type": "ephemeral"}}]


_CHART_DATA_LOADERS = {
    "checkins_by_time": checkins_by_time,
    "popular_classes": popular_classes,
    "membership_plans": membership_plans,
    "signups_by_month": signups_by_month,
    "active_vs_cancelled": active_vs_cancelled,
}


def _chart_data(data_source):
    loader = _CHART_DATA_LOADERS.get(data_source)
    return loader() if loader else None


def _data_for_claude(data_source, payload):
    """Return a condensed, analysis-friendly view of payload for Claude to reason about."""
    if "x" in payload and "y" in payload:
        xs, ys = payload["x"], payload["y"]
        if not ys:
            return {"items": [], "total": 0}
        max_idx = ys.index(max(ys))
        min_idx = ys.index(min(ys))
        return {
            "items": list(zip(xs, ys)),
            "total": sum(ys),
            "max": {"label": xs[max_idx], "value": ys[max_idx]},
            "min": {"label": xs[min_idx], "value": ys[min_idx]},
        }
    if "labels" in payload and "values" in payload:
        labels, values = payload["labels"], payload["values"]
        total = sum(values)
        return {
            "breakdown": [
                {"label": l, "value": v,
                 "pct": round(v / total * 100) if total else 0}
                for l, v in zip(labels, values)
            ],
            "total": total,
        }
    return payload
1

def ai_response(prompt, history=None):
    if not prompt or not prompt.strip():
        yield "Please type a message..."
        return

    user_input = prompt.strip().lower()
    global new_class_signups_count

    # Track state changes that are reflected in the UI
    if 'signup' in user_input:
        new_class_signups_count += 1

    if "signup" in user_input:
        time.sleep(random.uniform(1.2, 2.0))
        lines = [
            "Got it — signing Mia Watts up for ALO + Wild Thing: Reset and Renewal.",
            "",
            "• Customer: Mia Watts  ·  mia.watts@email.com",
            "• Class: ALO + Wild Thing: Reset and Renewal",
            f"• Date: {(lambda d: d.strftime('%b ') + str(d.day) + ', ' + d.strftime('%Y'))(date.today() + timedelta(days=1))}  ·  10:00 AM",
            "• Spots remaining after signup: 19 of 20",
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

            # Chart tool is always attached so Claude can visualise eagerly.
            # Email/class tools stay gated — they trigger page redirects.
            _chart_keywords = {"chart", "graph", "plot", "show", "visuali", "trend",
                               "breakdown", "popular", "busiest", "busy", "member",
                               "signup", "sign-up", "sign up", "cancel", "renewal",
                               "active", "checkin", "check-in", "checked", "plan"}
            _email_action_keywords = {"make", "write", "draft", "compose", "create", "generate"}
            _class_action_keywords = {"create", "new", "add", "schedule", "set up"}
            wants_chart = any(kw in user_input for kw in _chart_keywords)
            wants_email = "email" in user_input and any(kw in user_input for kw in _email_action_keywords)
            wants_class = (
                any(kw in user_input for kw in _class_action_keywords)
                and any(kw in user_input for kw in {"class", "event", "session"})
            ) or user_input == "class"

            _td = date.today()
            _today_str = _td.strftime('%b ') + str(_td.day) + ', ' + _td.strftime('%Y')
            tools_arg = []
            for _t in TOOLS:
                if _t["name"] == "generate_chart":
                    tools_arg.append(_t)
                elif _t["name"] == "compose_email" and wants_email:
                    tools_arg.append(_t)
                elif _t["name"] == "create_class" and wants_class:
                    import copy
                    _patched = copy.deepcopy(_t)
                    _patched["input_schema"]["properties"]["date"]["description"] += f" Today is {_today_str}."
                    tools_arg.append(_patched)

            # Pin the tool by name when intent is unambiguous, so the eagerly-
            # attached generate_chart tool can't steal the call.
            if wants_class and not wants_chart and not wants_email:
                tool_choice_arg = {"type": "tool", "name": "create_class"}
            elif wants_email and not wants_chart and not wants_class:
                tool_choice_arg = {"type": "tool", "name": "compose_email"}
            else:
                tool_choice_arg = anthropic.NOT_GIVEN

            # Phase 1: stream — detects whether Claude wants a chart
            with anthropic_client.messages.stream(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=_system_block(),
                tools=tools_arg,
                tool_choice=tool_choice_arg,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield text
                final = stream.get_final_message()

            tool_block = next(
                (b for b in final.content if b.type == "tool_use"),
                None,
            )

            if tool_block and tool_block.name == "generate_chart":
                inp = tool_block.input
                data = _chart_data(inp["data_source"])
                if data is None:
                    yield "\nData for that metric isn't available yet."
                    return

                # Build the assistant turn to send back (required by the API)
                assistant_content = []
                for block in final.content:
                    if block.type == "text":
                        assistant_content.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        assistant_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })

                # Phase 2: return real data so Claude writes an informed summary
                follow_up = messages + [
                    {"role": "assistant", "content": assistant_content},
                    {
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": tool_block.id,
                            "content": json.dumps(_data_for_claude(inp["data_source"], data)),
                        }],
                    },
                ]
                with anthropic_client.messages.stream(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=512,
                    system=_system_block(),
                    messages=follow_up,
                ) as stream2:
                    for text in stream2.text_stream:
                        yield text

                # Yield the chart after the summary
                yield "__CHART__" + json.dumps(build_chart_spec(inp["chart_type"], data))

            elif tool_block and tool_block.name == "compose_email":
                inp = tool_block.input
                subject = inp.get("subject", "")
                body = inp.get("body", "")
                yield "Draft ready — opening the email editor now.\n"
                yield "__EMAIL__" + json.dumps({"subject": subject, "body": body})
                yield "__REDIRECT__email"

            elif tool_block and tool_block.name == "create_class":
                new_class_signups_count = 0
                inp = tool_block.input
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

        except Exception:
            yield "Sorry, something went wrong. Please try again."
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
    if "signup" in user_input:
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
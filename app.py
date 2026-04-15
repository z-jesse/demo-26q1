import json
import os
import random
import time
from datetime import date, timedelta

import anthropic
from flask import Flask, render_template, request, jsonify, stream_with_context, Response, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
SITE_PASSWORD = os.environ.get("SITE_PASSWORD", "vygor")

anthropic_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = (
    "You are Vygor Intelligence, an AI assistant built into Vygor, a studio management "
    "platform for yoga and fitness businesses. You help owners with analytics, scheduling, "
    "customer management, and marketing. Keep responses concise and actionable — 2 to 5 "
    "sentences or a short bullet list using the bullet character •. Do not use markdown "
    "asterisks for bold text. The studio in this demo is a yoga studio called 'Vygor Test'."
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

CHART_TOOLS = [
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
                    "enum": ["line", "bar", "heatmap", "donut"],
                    "description": "Plotly chart type to render.",
                },
                "data_source": {
                    "type": "string",
                    "enum": ["average_spend_by_week", "visit_heatmap"],
                    "description": (
                        "Which dataset to use. "
                        "average_spend_by_week: weekly avg spend per customer (line chart). "
                        "visit_heatmap: visit counts by day-of-week and hour (heatmap)."
                    ),
                },
            },
            "required": ["chart_type", "data_source"],
        },
        "cache_control": {"type": "ephemeral"},
    }
]

_SYSTEM_BLOCK = [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]


def _stub_data(data_source):
    """Placeholder data until data.py is wired in."""
    if data_source == "average_spend_by_week":
        return {
            "x": ["Jan 1", "Jan 8", "Jan 15", "Jan 22", "Jan 29"],
            "y": [58, 72, 85, 92, 108],
        }
    if data_source == "visit_heatmap":
        days = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
        hours = ["6 AM", "7 AM", "8 AM", "9 AM", "10 AM", "11 AM",
                 "12 PM", "1 PM", "2 PM", "3 PM", "4 PM", "5 PM", "6 PM"]
        z = []
        for h in range(13):
            row = []
            is_peak = 0 <= h <= 3
            is_dip = 5 <= h <= 7
            is_afternoon = 8 <= h <= 10
            is_evening = 11 <= h <= 12
            for d in range(7):
                weekend = d in (0, 6)
                base = 35 if weekend else 22
                if is_peak:
                    base += 55 if weekend else 38
                elif is_dip:
                    base -= 12
                elif is_afternoon:
                    base += 15
                elif is_evening:
                    base += 18
                noise = (random.random() - 0.5) * 24
                row.append(max(8, min(98, round(base + noise))))
            z.append(row)
        return {"x": days, "y": hours, "z": z}
    return None


def _data_for_claude(data_source, data):
    """Return a condensed, analysis-friendly version of data for Claude to reason about."""
    if data_source == "average_spend_by_week":
        ys = data["y"]
        change_pct = round((ys[-1] - ys[0]) / ys[0] * 100)
        return {
            "weeks": list(zip(data["x"], ys)),
            "min": min(ys),
            "max": max(ys),
            "change_pct": change_pct,
        }
    if data_source == "visit_heatmap":
        days, hours, z = data["x"], data["y"], data["z"]
        day_totals = {
            days[d]: sum(z[h][d] for h in range(len(hours)))
            for d in range(len(days))
        }
        hour_totals = {
            hours[h]: sum(z[h][d] for d in range(len(days)))
            for h in range(len(hours))
        }
        return {"day_totals": day_totals, "hour_totals": hour_totals}
    return data


def ai_response(prompt, history=None):
    if not prompt or not prompt.strip():
        yield "Please type a message..."
        return

    user_input = prompt.strip().lower()
    global new_class_signups_count

    # Track state changes that are reflected in the UI
    if all(word in user_input for word in ['create', 'new']):
        new_class_signups_count = 0
    elif 'signup' in user_input:
        new_class_signups_count += 1

    if all(word in user_input for word in ['create', 'new']) or user_input == "class":
        time.sleep(random.uniform(1.5, 2.5))
        _tmrw = date.today() + timedelta(days=1)
        _tmrw_str = _tmrw.strftime('%b ') + str(_tmrw.day) + ', ' + _tmrw.strftime('%Y')
        lines = [
            "On it — building a class template for you.",
            "",
            "• Name: VIP Yoga Event - 2026",
            f"• Date: {_tmrw_str}  ·  10:00 AM  ·  60 min",
            "• Max participants: 20  ·  Price: $0",
            "",
            "Opening the form now…",
        ]
        for line in lines:
            yield line + "\n"
            time.sleep(random.uniform(0.05, 0.15))
        return

    elif "signup" in user_input:
        time.sleep(random.uniform(1.2, 2.0))
        lines = [
            "Got it — signing Mia Watts up for VIP Yoga Event - 2026.",
            "",
            "• Customer: Mia Watts  ·  mia.watts@email.com",
            "• Class: VIP Yoga Event - 2026",
            f"• Date: {(lambda d: d.strftime('%b ') + str(d.day) + ', ' + d.strftime('%Y'))(date.today() + timedelta(days=1))}  ·  10:00 AM",
            "• Spots remaining after signup: 19 of 20",
            "",
            "Done — class roster updated.",
        ]
        for line in lines:
            yield line + "\n"
            time.sleep(random.uniform(0.05, 0.15))
        return

    elif "email" in user_input:
        time.sleep(random.uniform(2.0, 3.5))
        lines = [
            "Generating a promotional email for the VIP Yoga Event.",
            "",
            "• Subject: You're invited — VIP Yoga Event 2026",
            "• Audience: All active members",
            "• Tone: Warm, exclusive, action-oriented",
            "• Key details: date, early-bird pricing, limited spots",
            "",
            "Draft ready — opening the email editor now.",
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

            # Only attach tools when the prompt looks chart-related
            _chart_keywords = {"chart", "graph", "plot", "show", "visuali", "trend",
                               "breakdown", "heatmap", "spend", "visit", "popular", "busiest"}
            wants_chart = any(kw in user_input for kw in _chart_keywords)
            tools_arg = CHART_TOOLS if wants_chart else anthropic.NOT_GIVEN

            # Phase 1: stream — detects whether Claude wants a chart
            with anthropic_client.messages.stream(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=_SYSTEM_BLOCK,
                tools=tools_arg,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield text
                final = stream.get_final_message()

            tool_block = next(
                (b for b in final.content if b.type == "tool_use" and b.name == "generate_chart"),
                None,
            )

            if tool_block:
                inp = tool_block.input
                data = _stub_data(inp["data_source"])
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
                    system=_SYSTEM_BLOCK,
                    messages=follow_up,
                ) as stream2:
                    for text in stream2.text_stream:
                        yield text

                # Yield the chart after the summary
                opts = {}
                if inp["data_source"] == "average_spend_by_week":
                    opts["y_prefix"] = "$"
                yield "__CHART__" + json.dumps(build_chart_spec(inp["chart_type"], data, opts))

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
    if user_input == "class" or all(w in user_input for w in ("create", "new")):
        redirect_after_stream = "new_class"
    elif "signup" in user_input:
        redirect_after_stream = "center=classes&new=1"
    elif "email" in user_input:
        redirect_after_stream = "email"
    else:
        redirect_after_stream = None

    def event_stream():
        for chunk in ai_response(prompt, history=history):
            if chunk.startswith("__CHART__"):
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
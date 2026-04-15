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

    if "average" in user_input and "spend" in user_input:
        time.sleep(random.uniform(6, 8))
        lines = [
            "Here’s average spend per customer over the last few weeks.",
            "",
            "Average spend has increased 86% to $108 over the period.",
            "",
        ]
        for line in lines:
            yield line + "\n"
            time.sleep(random.uniform(0.1, 0.3))
        chart_spec = {
            "data": [{
                "x": ["Jan 1", "Jan 8", "Jan 15", "Jan 22", "Jan 29"],
                "y": [58, 72, 85, 92, 108],
                "type": "scatter",
                "mode": "lines",
                "fill": "tozeroy",
                "fillcolor": "rgba(4, 152, 224, 0.4)",
                "fillgradient": {
                    "type": "vertical",
                    "colorscale": [[0, "rgba(4, 152, 224, 0)"], [1, "rgba(4, 152, 224, 0.3)"]]
                },
                "line": {"color": "#0498e0", "width": 2}
            }],
            "layout": {
                "margin": {"t": 0, "r": 8, "b": 24, "l": 40},
                "autosize": True,
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "xaxis": {
                    "tickfont": {"color": "rgba(122, 122, 122, 1)", "size": 12, "family": "Figtree"},
                    "showgrid": False,
                    "zeroline": False
                },
                "yaxis": {
                    "tickfont": {"color": "rgba(122, 122, 122, 1)", "size": 12, "family": "Figtree"},
                    "gridcolor": "rgba(61, 61, 61, 1)",
                    "zeroline": False,
                    "tickprefix": "$"
                },
                "showlegend": False
            }
        }
        yield "__CHART__" + json.dumps(chart_spec)
        return

    elif "schedule" in user_input and "class" in user_input:
        time.sleep(random.uniform(2, 4))
        lines = [
            "Here's visit distribution by day and time (when people come in).",
            "",
            "Schedule most of your classes on weekend mornings (6–9 AM Sat/Sun) and weekday mornings (6–9 AM) — that's when visits peak.",
            "",
        ]
        for line in lines:
            yield line + "\n"
            time.sleep(random.uniform(0.1, 0.3))
        days = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
        hours = ["6 AM", "7 AM", "8 AM", "9 AM", "10 AM", "11 AM", "12 PM", "1 PM", "2 PM", "3 PM", "4 PM", "5 PM", "6 PM"]
        z = []
        for h in range(13):
            row = []
            is_peak_morning = 0 <= h <= 3
            is_lunch_dip = 5 <= h <= 7
            is_afternoon = 8 <= h <= 10
            is_evening_bump = 11 <= h <= 12
            for d in range(7):
                is_weekend = d in (0, 6)
                base = 35 if is_weekend else 22
                if is_peak_morning:
                    base += 55 if is_weekend else 38
                elif is_lunch_dip:
                    base -= 12
                elif is_afternoon:
                    base += 15
                elif is_evening_bump:
                    base += 18
                noise = (random.random() - 0.5) * 24
                row.append(max(8, min(98, round(base + noise))))
            z.append(row)
        heatmap_spec = {
            "data": [{
                "z": z,
                "x": days,
                "y": hours,
                "type": "heatmap",
                "colorscale": [[0, "rgba(4, 152, 224, 0.15)"], [0.5, "rgba(4, 152, 224, 0.5)"], [1, "rgba(4, 152, 224, 0.9)"]],
                "showscale": False
            }],
            "layout": {
                "margin": {"t": 8, "r": 8, "b": 36, "l": 56},
                "autosize": True,
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "xaxis": {
                    "tickvals": list(range(7)),
                    "ticktext": days,
                    "side": "bottom",
                    "tickfont": {"color": "rgba(122, 122, 122, 1)", "size": 12, "family": "Figtree"},
                    "showline": False,
                    "showgrid": False
                },
                "yaxis": {
                    "tickvals": list(range(13)),
                    "ticktext": hours,
                    "tickfont": {"color": "rgba(122, 122, 122, 1)", "size": 12, "family": "Figtree"},
                    "showline": False,
                    "showgrid": False
                },
                "font": {"family": "Figtree"},
                "showlegend": False
            }
        }
        yield "__CHART__" + json.dumps(heatmap_spec)
        return

    else:
        try:
            messages = []
            if history:
                for m in history:
                    role = m.get("role", "")
                    content = m.get("content", "")
                    if role in ("user", "assistant") and content:
                        messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": prompt.strip()})
            with anthropic_client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=512,
                system=SYSTEM_PROMPT,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield text
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
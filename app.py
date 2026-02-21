import json
import os
import random
import time
from datetime import date, timedelta

from flask import Flask, render_template, request, jsonify, stream_with_context, Response, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
SITE_PASSWORD = os.environ.get("SITE_PASSWORD", "vygor")


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


def get_redirect_center(prompt):
    """Return the center key to redirect to for this prompt, or None."""
    if not prompt or not prompt.strip():
        return None
    user_input = prompt.strip().lower()
    if user_input == "class":
        return "new_class"
    if all(w in user_input for w in ("create", "new")):
        return "new_class"
    return None


def ai_response(prompt):
    if not prompt or not prompt.strip():
        yield "Please type a message..."
        return

    user_input = prompt.strip().lower()
    global new_class_signups_count

    if 'classes' in user_input and 'profitable' in user_input:
        time.sleep(random.uniform(2, 4))
        lines = [
            "The most profitable classes last quarter were:",
            "• Yoga Flow — $6,540",
            "• Evening Meditation — $4,800",
            "• Power Pose — $1,380",
            "Net profit from top 3: $12,720"
        ]

    elif all(word in user_input for word in ['create', 'new']):
        new_class_signups_count = 0
        time.sleep(random.uniform(4, 6))
        lines = [
            "✅ Creating a new event for VIPs.",
            "",
            "I've set up a draft event.",
            "You can edit the details (date, time, capacity) and save it to your calendar.",
            "",
        ]

    elif all(word in user_input for word in ['signup']):
        time.sleep(random.uniform(2, 4))
        new_class_signups_count += 1
        lines = [
            "Retrieving customer analytics...",
            "Your top customer based on attendance is **Mia Watts** 🎖️",
            "",
            f"✅ Just scheduled **Mia Watts** for the **VIP Yoga Event - 2026** tomorrow at 10:00 AM.",
            "Confirmation email has been sent to them."
        ]

    elif all(word in user_input for word in ['email']):
        time.sleep(random.uniform(6, 8))
        lines = [
            "I've drafted a personalized marketing email for your **VIP Yoga Event - 2026** tomorrow at 10:00 AM 🎉",
            "It's targeted at your most loyal customers based on attendance — the ones who come back the most often.",
            "",
            "The email highlights their loyalty, offers exclusive first access, and includes a clear 'YES' reply / button to reserve their limited spot.",
            "",
            "You'll be redirected to review the full draft. Let me know if you want any changes to the wording, subject line, tone, or anything else before it goes out! 😊"
        ]

    elif "chart" in user_input:
        time.sleep(random.uniform(1, 2))
        lines = [
            "Here’s a quick view of total sales over the last few weeks.",
            "",
        ]
        for line in lines:
            yield line + "\n"
            time.sleep(random.uniform(0.1, 0.3))
        chart_spec = {
            "data": [{
                "x": ["Jan 1", "Jan 8", "Jan 15", "Jan 22", "Jan 29"],
                "y": [770, 940, 1100, 1030, 1250],
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

    else:
        lines = [
            "Sorry, something went wrong. Please try again."
        ]

    for line in lines:
        yield line + "\n"
        time.sleep(random.uniform(0.1, 0.5))


@app.route('/api/stream', methods=['GET', 'POST'])
def stream_prompt():
    # Handle prompt from either GET query string or POST JSON body
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        prompt = (data.get('prompt') or '').strip()
    else:  # GET
        prompt = (request.args.get('prompt') or '').strip()

    if not prompt:
        def empty_gen():
            yield "data: Please type a message...\n\n"
        return Response(stream_with_context(empty_gen()), mimetype="text/event-stream")

    redirect_center = get_redirect_center(prompt)
    if redirect_center and redirect_center not in CENTER_TEMPLATES:
        redirect_center = None

    user_input = prompt.strip().lower()
    if "signup" in user_input:
        redirect_after_stream = "center=classes&new=1"
    elif "email" in user_input:
        redirect_after_stream = "email"
    else:
        redirect_after_stream = None

    def event_stream():
        yield "data: <span class=\"thinking\">Thinking...</span><br>\n\n"

        for chunk in ai_response(prompt):
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

        if redirect_center:
            yield f"data: __REDIRECT__{redirect_center}\n\n"
        elif redirect_after_stream:
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
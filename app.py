from flask import Flask, render_template, request, jsonify, stream_with_context, Response

app = Flask(__name__)

CENTER_TEMPLATES = {
    "dashboard": "center/dashboard.html",
    "email": "center/email.html",
}

def ai_response(prompt):
    if not prompt or not prompt.strip():
        yield "Please type a message..."
        return

    user_input = prompt.strip().lower()

    if 'classes' in user_input and 'profitable' in user_input:
        lines = [
            "The most profitable classes last quarter were:",
            "• Yoga Flow — $5,200",
            "• HIIT Blast — $4,800",
            "• Pilates Reformer — $3,900",
            "Total revenue from top 3: $13,900"
        ]

    elif all(word in user_input for word in ['schedule', 'flow class', 'wednesday']):
        name = "John James" if 'john' in user_input or 'james' in user_input else "the requested member"
        lines = [
            f"✅ Scheduled {name} for Flow Class this Wednesday at 6:00 PM.",
            "A confirmation has been sent to their email."
        ]

    elif all(word in user_input for word in ['draft', 'email', 'loyal', 'customers', 'event']):
        lines = [
            "📧 Draft created and sent to your most loyal customers (top 50 by visits):",
            "",
            "Subject: You're Invited – Exclusive Preview of Our New Event 🎉",
            "",
            "Dear valued member,",
            "",
            "Because you've been with us through so many flows, lifts and stretches,",
            "we're giving you first access to our new 'Reset & Recharge Weekend' event",
            "happening February 14–15, 2026.",
            "",
            "Limited spots — reply 'YES' or click below to reserve.",
            "",
            "See you on the mat!",
            "Jesse & the Team",
            "",
            "[ Reserve My Spot ]",
            "",
            "(Sent to 50 recipients)"
        ]

    else:
        lines = [
            "Sorry, I didn't understand that command.",
            "",
            "This demo recognizes these example prompts:",
            "• what classes were most profitable",
            "• schedule John James for Flow Class this wednesday",
            "• draft and email to my most loyal customers inviting them to a new event",
            "",
            "Try typing one of those!"
        ]

    # Small random thinking delay (0.4–1.8 sec) before any output
    import random, time
    time.sleep(random.uniform(0.4, 1.8))

    for line in lines:
        yield line + "\n"
        time.sleep(random.uniform(0.06, 0.18))   # typing speed ~60–160 ms per line


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

    def event_stream():
        yield "data: <span class=\"thinking\">Thinking...</span><br>\n\n"

        for chunk in ai_response(prompt):
            safe = (
                chunk
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
            )
            yield f"data: {safe}\n\n"

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache"}
    )


@app.route('/', methods=['GET', 'POST'])
def home():
    response = None
    user_prompt = None

    center = (request.args.get('center') or 'dashboard').strip().lower()
    center_key = center if center in CENTER_TEMPLATES else "dashboard"
    center_template = CENTER_TEMPLATES[center_key]

    if request.method == 'POST':
        user_prompt = request.form.get('prompt', '').strip()
        if user_prompt:
            response = ai_response(user_prompt)

    return render_template('index.html', 
                          response=response,
                          user_prompt=user_prompt,
                          center_template=center_template,
                          center_key=center_key)


if __name__ == "__main__":
    app.run(debug=True)
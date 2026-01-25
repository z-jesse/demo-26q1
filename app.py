from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

def ai_response(prompt):
    """
    Hardcoded intent recognizer for the 3 demo prompts.
    Returns plain text (with newlines) that looks good in <pre> or similar.
    """
    if not prompt or not prompt.strip():
        return "Please type a message..."

    user_input = prompt.strip().lower()

    # Intent 1: "what classes were most profitable"
    if 'classes' in user_input and 'profitable' in user_input:
        return (
            "The most profitable classes last quarter were:\n"
            "• Yoga Flow — $5,200\n"
            "• HIIT Blast — $4,800\n"
            "• Pilates Reformer — $3,900\n"
            "Total revenue from top 3: $13,900"
        )

    # Intent 2: schedule ... Flow Class ... wednesday
    elif all(word in user_input for word in ['schedule', 'flow class', 'wednesday']):
        # For demo we hardcode the name — in real app you'd parse it
        name = "John James" if 'john' in user_input or 'james' in user_input else "the requested member"
        return (
            f"✅ Scheduled {name} for Flow Class this Wednesday at 6:00 PM.\n"
            "A confirmation has been sent to their email."
        )

    # Intent 3: draft and email ... loyal customers ... event
    elif all(word in user_input for word in ['draft', 'email', 'loyal', 'customers', 'event']):
        return (
            "📧 Draft created and sent to your most loyal customers (top 50 by visits):\n\n"
            "Subject: You're Invited – Exclusive Preview of Our New Event 🎉\n\n"
            "Dear valued member,\n\n"
            "Because you've been with us through so many flows, lifts and stretches, "
            "we're giving you first access to our new 'Reset & Recharge Weekend' event "
            "happening February 14–15, 2026.\n\n"
            "Limited spots — reply 'YES' or click below to reserve.\n\n"
            "See you on the mat!\nJesse & the Team\n\n"
            "[ Reserve My Spot ]\n\n"
            "(Sent to 50 recipients)"
        )

    # Fallback for unrecognized input
    else:
        return (
            "Sorry, I didn't understand that command.\n\n"
            "This demo recognizes these example prompts:\n"
            "• what classes were most profitable\n"
            "• schedule John James for Flow Class this wednesday\n"
            "• draft and email to my most loyal customers inviting them to a new event\n\n"
            "Try typing one of those!"
        )


@app.route('/', methods=['GET', 'POST'])
def home():
    response = None
    user_prompt = None

    if request.method == 'POST':
        user_prompt = request.form.get('prompt', '').strip()
        if user_prompt:
            response = ai_response(user_prompt)

    return render_template('index.html', 
                          response=response,
                          user_prompt=user_prompt)


@app.post('/api/prompt')
def api_prompt():
    payload = request.get_json(silent=True) or {}
    prompt = (payload.get('prompt') or request.form.get('prompt') or '').strip()
    return jsonify(
        prompt=prompt,
        response=ai_response(prompt),
    )


if __name__ == "__main__":
    app.run(debug=True)
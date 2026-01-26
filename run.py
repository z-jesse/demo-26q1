# run.py
import sys
import os
import webbrowser
import threading
from app import app  # ← import your Flask app object

def open_browser():
    # Wait a little so server has time to start
    import time
    time.sleep(1.5)
    port = int(os.getenv("PORT", 5000))
    webbrowser.open(f"http://127.0.0.1:{port}")

if __name__ == "__main__":
    # Start browser in background thread
    threading.Thread(target=open_browser, daemon=True).start()

    debug = "--debug" in sys.argv
    port = int(os.getenv("PORT", 5000))

    app.run(host="127.0.0.1", port=port, debug=debug, use_reloader=False)
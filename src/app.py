from flask import Flask, jsonify, render_template, request, redirect, url_for, Response
from wakeonlan import send_magic_packet
from functools import wraps
import requests
import os
from datetime import datetime, timezone

app = Flask(__name__)

MAC = os.environ.get('MAC')
IP = os.environ.get('IP')

USERNAME = os.environ.get('WOL_USERNAME')
PASSWORD = os.environ.get('WOL_PASSWORD')

STATUSCAKE_API_KEY = os.environ.get("STATUSCAKE_API_KEY")
STATUSCAKE_TEST_ID = os.environ.get("STATUSCAKE_TEST_ID")

def check_auth(username, password):
    return username == USERNAME and password == PASSWORD

def authenticate():
    return Response(
        "Login required.", 401,
        {"WWW-Authenticate": 'Basic realm="Login Required"'}
    )

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

def fetch_statuscake_periods(api_key, test_id, n=20):
    url = f"https://api.statuscake.com/v1/uptime/{test_id}/periods?limit={n}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json().get("data", [])
        return data
    except Exception:
        return []

def create_period_segments(periods):
    segments = []
    for entry in reversed(periods):
        status = entry['status']
        start = entry.get("created_at")
        end = entry.get("ended_at") or datetime.now(timezone.utc).isoformat()
        segments.append({"status": status, "start": start, "end": end})
    return segments

@app.route("/")
@requires_auth
def index():
    periods = fetch_statuscake_periods(STATUSCAKE_API_KEY, STATUSCAKE_TEST_ID, n=20)
    segments = create_period_segments(periods)
    chart_labels = []
    chart_values = []
    for seg in segments:
        y = 1 if seg["status"] == "up" else 0
        chart_labels.append(seg["start"])
        chart_values.append(y)
        chart_labels.append(seg["end"])
        chart_values.append(y)
    return render_template('index.html',
                           chart_labels=chart_labels,
                           chart_values=chart_values)

@app.route("/send-wol/", methods=["POST"])
@requires_auth
def send_wol():
    send_magic_packet(MAC, ip_address=IP)
    return redirect(url_for('index'))

@app.route("/wake", methods=["POST"])
@requires_auth
def wake():
    send_magic_packet(MAC, ip_address=IP)
    return '', 200

@app.route("/health", methods=["GET"])
def health_check():
    health_data = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "wol-app",
        "version": "1.0.0"
    }
    return jsonify(health_data), 200

@app.route("/check-emby", methods=["GET"])
@requires_auth
def check_emby_server():
    import socket

    def can_reach_server(hostname, port, timeout=5):
        try:
            with socket.create_connection((hostname, port), timeout=timeout):
                return True
        except Exception:
            return False

    is_reachable = can_reach_server("emby.snackk-media.com", 443)

    response_data = {
        "reachable": is_reachable,
        "server": "emby.snackk-media.com",
        "port": 443,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    return jsonify(response_data), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)

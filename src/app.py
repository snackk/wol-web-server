from flask import Flask, jsonify, render_template, request, redirect, url_for, Response
from functools import wraps
import requests
import os
from datetime import datetime, timezone

app = Flask(__name__)

USERNAME = os.environ.get('WOL_USERNAME')
PASSWORD = os.environ.get('WOL_PASSWORD')

STATUSCAKE_API_KEY = os.environ.get("STATUSCAKE_API_KEY")
STATUSCAKE_TEST_ID = os.environ.get("STATUSCAKE_TEST_ID")

AC_MAP = {
    'sala': 'living-room.local',
    'suite': 'suite.local',
    'escritorio': 'office.local',
    'cozinha': 'kitchen.local',
    'visitas': 'guest-room.local'
}

SWITCHES_MAP = {
    'gaming': 'pc-switch.local'
}

MODE_MAP = {
    'cool': 'COOL',
    'heat': 'HEAT',
    'fan': 'FAN_ONLY',
    'dry': 'DRY',
    'auto': 'HEAT_COOL'
}

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
    hostname = SWITCHES_MAP['gaming']
    state = 'ON'
    target_url = f"http://{hostname}/api/state/{state}"

    try:
        requests.put(target_url, timeout=5)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return redirect(url_for('index'))

@app.route("/wake", methods=["POST"])
@requires_auth
def wake():
    hostname = SWITCHES_MAP['gaming']
    state = 'ON'
    target_url = f"http://{hostname}/api/state/{state}"

    try:
        requests.put(target_url, timeout=5)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
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

@app.route("/climate", methods=["POST"])
def set_climate():
    data = request.json
    room_id = data.get('roomId')
    mode = data.get('mode')
    temp = data.get('temp')
    status = data.get('status')

    if room_id not in AC_MAP:
        return jsonify({"error": "Room not found!"}), 404

    hostname = AC_MAP[room_id]

    api_mode = 'OFF' if status == 'off' else MODE_MAP.get(mode, 'COOL')

    target_url = f"http://{hostname}/climate/air_conditioner/set"
    params = {
        "mode": api_mode,
        "temp": temp
    }

    try:
        if api_mode == 'OFF':
            response = requests.post(target_url, params={"mode": "OFF"}, timeout=5)
        else:
            response = requests.post(target_url, params=params, timeout=5)

        return jsonify({
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "target": target_url
        }), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)

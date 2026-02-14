from flask import Flask, jsonify, render_template, request, redirect, url_for, Response, send_from_directory, session
from functools import wraps
import requests
import os
import secrets
from datetime import datetime, timezone, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.permanent_session_lifetime = timedelta(days=31)

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/logo.png')
def serve_logo():
    return send_from_directory('static', 'logo.png')

@app.route("/gata")
def serve_gata():
    return send_from_directory('static', 'gata.html')

@app.route("/task")
def serve_task():
    return send_from_directory('static', 'task.html')

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

REVERSE_MODE_MAP = {
    'COOL': 'cool',
    'HEAT': 'heat',
    'FAN_ONLY': 'fan',
    'DRY': 'dry',
    'HEAT_COOL': 'auto',
    'OFF': 'off'
}

INT_MODE_MAP = {
    1: 'auto',
    2: 'cool',
    3: 'dry',
    4: 'heat',
    5: 'fan',
    0: 'off'
}

def check_auth(username, password):
    if not USERNAME or not PASSWORD:
        return False
    return username == USERNAME and password == PASSWORD

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if check_auth(username, password):
            session.permanent = True
            session['authenticated'] = True
            next_page = request.args.get('next')
            if next_page and not next_page.startswith('/'):
                next_page = None
            return redirect(next_page or url_for('index'))
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')


@app.route("/logout")
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login'))


@app.route("/")
@requires_auth
def index():
    return render_template('index.html')


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


@app.route("/switch/<device_id>/<state>", methods=["POST"])
@requires_auth
def toggle_switch(device_id, state):
    if device_id not in SWITCHES_MAP:
        return jsonify({"error": "Switch not found"}), 404
    
    if state.upper() not in ["ON", "OFF"]:
        return jsonify({"error": "Invalid state"}), 400

    hostname = SWITCHES_MAP[device_id]
    target_url = f"http://{hostname}/api/state/{state.upper()}"

    try:
        requests.put(target_url, timeout=5)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return '', 200


@app.route("/climate/status", methods=["GET"])
@requires_auth
def climate_status():
    import socket
    results = {
        "devices": {}, 
        "switches": {},
        "averages": {"indoor": None, "outdoor": None}
    }
    indoor_temps = []
    outdoor_temps = []
    
    # Check ACs
    for room_id, hostname in AC_MAP.items():
        try:
            # First try the status API
            status_url = f"http://{hostname}/api/status"
            r = requests.get(status_url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                indoor = data.get("indoor_temp")
                outdoor = data.get("outdoor_temp")
                
                if indoor is not None:
                    indoor_temps.append(indoor)
                if outdoor is not None:
                    outdoor_temps.append(outdoor)

                results["devices"][room_id] = {
                    "power": data.get("power", False),
                    "temp": indoor if indoor is not None else data.get("temp"),
                    "target": data.get("temp"),
                    "mode": INT_MODE_MAP.get(data.get("mode"), REVERSE_MODE_MAP.get(data.get("state"), "cool")),
                    "online": True
                }
            else:
                results["devices"][room_id] = {"online": False}
        except Exception:
            results["devices"][room_id] = {"online": False}
    
    # Check Switches (Gaming PC status via Emby check)
    def can_reach_server(hostname, port, timeout=3):
        try:
            with socket.create_connection((hostname, port), timeout=timeout):
                return True
        except Exception:
            return False

    is_emby_reachable = can_reach_server("emby.snackk-media.com", 443)
    results["switches"]["gaming"] = {
        "status": "ON" if is_emby_reachable else "OFF",
        "name": "Gaming PC"
    }

    if indoor_temps:
        results["averages"]["indoor"] = round(sum(indoor_temps) / len(indoor_temps), 1)
    if outdoor_temps:
        results["averages"]["outdoor"] = round(sum(outdoor_temps) / len(outdoor_temps), 1)
        
    return jsonify(results)


@app.route("/climate", methods=["POST"])
def set_climate():
    data = request.json
    room_id = data.get('roomId')
    status = data.get('status')

    if room_id not in AC_MAP:
        return jsonify({"error": "Room not found!"}), 404

    hostname = AC_MAP[room_id]
    target_url = f"http://{hostname}/api/state/{status}"

    try:
        response = requests.put(target_url, timeout=5)
        device_response = {}
        try:
            device_response = response.json()
        except Exception:
            pass

        return jsonify({
            "success": response.status_code == 200 and device_response.get("success", True),
            "status_code": response.status_code,
            "device_response": device_response,
            "target": target_url
        }), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health_check():
    health_data = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
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
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }

    return jsonify(response_data), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)

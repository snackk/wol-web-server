from flask import Flask, render_template_string, request, redirect, url_for, Response
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
    return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>snack-media</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://code.getmdl.io/1.3.0/material.deep_purple-indigo.min.css">
<script defer src="https://code.getmdl.io/1.3.0/material.min.js"></script>
<link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Roboto:400,700">
<link rel="stylesheet" href="https://fonts.googleapis.com/icon?family=Material+Icons">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 72 72'%3E%3Ctext y='56' font-size='56'%3E%E2%9A%A1%3C/text%3E%3C/svg%3E" type="image/svg+xml">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
html, body, .root-container {
  margin: 0; padding: 0; min-height: 100vh; background: linear-gradient(135deg, #667eea, #764ba2);
  font-family: 'Roboto', sans-serif; color: #fff;
}
.center-container {
  display: flex; align-items: center; justify-content: center; width: 100vw; height: 44vh;
}
.power-button-container {
  position: relative; width: 80px; height: 80px;
}
.power-container {
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  display: flex; align-items: center; justify-content: center;
}
.footer {
  position: fixed; left: 0; bottom: 0; width: 100%;
  text-align: center; padding: 16px 0; font-size: 14px; color: #d9d6ff;
  opacity: 0.97; background: transparent; z-index: 99;
}
.footer a { color: #b2b4fa; text-decoration: none; font-weight: bold; }
.footer a:hover { text-decoration: underline; color: #fff; }
.statuscake-graph-wrap {
  width: 98vw; max-width: 900px; margin: 0 auto; background: #ffffff0a;
  border-radius: 16px; box-shadow: 0 2px 13px rgba(80,74,152,0.13);
  padding: 0.8em 0.3em 1.4em 0.3em; margin-bottom: 25px;
  display: flex; flex-direction: column; align-items: center; /* Center box contents */
}
.statuscake-title {
  font-size: 1.01em; font-weight: 500; letter-spacing: 0.4px; margin-bottom: 0.9em; color: #efeefd; text-align: left;
  width: 100%; box-sizing: border-box; padding-left: 7px; padding-top: 8px;
}
#periodsChart {
  width: 100% !important;
  max-width: 100%;
  height: 220px !important;
  display: block;
  margin: 0 auto;
  background: transparent;
}
@media (max-width: 568px) {
  .center-container { height: 32vh; }
  .power-button-container { width: 54px; height: 54px; }
  .statuscake-graph-wrap { padding: 0.4em 1vw 1.1em 1vw; }
  #periodsChart { height: 160px !important; }
}
</style>
</head>
<body>
<div class="root-container">
  <div class="center-container">
    <form action="/send-wol/" method="POST">
      <div class="power-button-container">
        <button type="submit" class="mdl-button mdl-js-button mdl-button--fab mdl-js-ripple-effect mdl-shadow--8dp">
          <span class="power-container">
            <i class="material-icons">power_settings_new</i>
          </span>
        </button>
      </div>
    </form>
  </div>
  <div class="statuscake-graph-wrap">
    <div class="statuscake-title">Uptime periods history</div>
    <canvas id="periodsChart"></canvas>
    <div style="margin-top:6px;font-size:0.98em;opacity:0.77;text-align:left;width:100%;padding-left:7px;">
      <span style="display:inline-block;width:11px;height:11px;background:#24c361;border-radius:3px;margin-right:4px;vertical-align:middle"></span>Up
      <span style="display:inline-block;width:11px;height:11px;background:#ff5c5c;border-radius:3px;margin-left:20px;margin-right:4px;vertical-align:middle"></span>Down
    </div>
  </div>
  <div class="footer">
    Made by <a href="https://github.com/snackk" target="_blank">@snackk</a> with love <span style="font-size:1.1em;">❤️</span>
  </div>
</div>
<script>
const labels = {{ chart_labels|tojson }};
const values = {{ chart_values|tojson }};

const ctx = document.getElementById('periodsChart').getContext('2d');
new Chart(ctx, {
  type: 'line',
  data: {
    labels: labels.map(
      l => new Date(l).toLocaleString(undefined, {
            month:'short', day:'numeric', hour:'2-digit',minute:'2-digit'
        })
    ),
    datasets: [{
      label: 'Status',
      data: values,
      stepped: true,
      borderColor: function(context) {
        if (!context.chart) return null;
        const chartctx = context.chart.ctx;
        const width = context.chart.width;
        const gradient = chartctx.createLinearGradient(0, 0, width, 0);
        for(let i=0;i<values.length;i++) {
            let stop = i/(values.length-1||1);
            let color = values[i]===1 ? '#24c361' : '#ff5c5c';
            gradient.addColorStop(stop, color);
        }
        return gradient;
      },
      backgroundColor: function(context) {
        if (!context.chart) return null;
        const chartctx = context.chart.ctx;
        const width = context.chart.width;
        const gradient = chartctx.createLinearGradient(0, 0, width, 0);
        for(let i=0;i<values.length;i++) {
            let stop = i/(values.length-1||1);
            let color = values[i]===1 ? 'rgba(36,195,97,0.17)' : 'rgba(255,92,92,0.14)';
            gradient.addColorStop(stop, color);
        }
        return gradient;
      },
      borderWidth: 3,
      fill: true,
      pointRadius: 3,
      pointBackgroundColor: values.map(v => v===1 ? '#24c361' : '#ff5c5c'),
      pointBorderColor: values.map(v => v===1 ? '#24c361' : '#ff5c5c')
    }]
  },
  options: {
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
            label: function(ctx){
                return ctx.parsed.y === 1 ? "Up" : "Down";
            }
        }
      }
    },
    elements: {
      line: { borderJoinStyle: 'miter' },
      point: { pointStyle: 'circle' }
    },
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      y: {
        min: -0.1,
        max: 1.1,
        ticks: {
          stepSize: 1,
          color: '#efeefd',
          callback: function(value){ return value===1 ? "Up" : (value===0 ? "Down" : ""); }
        },
        grid: { color: 'rgba(255,255,255,0.12)' }
      },
      x: {
        grid: { color: 'rgba(255,255,255,0.08)' },
        ticks: { color: '#efeefd', autoSkip: true, maxTicksLimit: 13 }
      }
    }
  }
});
</script>
</body>
</html>
""", chart_labels=chart_labels, chart_values=chart_values)

@app.route("/send-wol/", methods=["POST"])
@requires_auth
def send_wol():
    send_magic_packet(MAC, ip_address=IP)
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)

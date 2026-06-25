import socket as _socket, os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from database import init_db, session_create, session_end, sessions_list, session_get

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

init_db()


def local_ip():
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close(); return ip
    except Exception:
        return "localhost"


# ── Pages ─────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", active="home", ip=local_ip())

@app.route("/draw")
def draw():
    return render_template("draw.html", active="draw")

@app.route("/cube")
def cube():
    return render_template("cube.html", active="cube")

@app.route("/phone3d")
def phone3d():
    return render_template("phone3d.html", active="phone3d")

@app.route("/drums")
def drums():
    return render_template("drums.html", active="drums")

@app.route("/sessions")
def sessions():
    return render_template("sessions.html", active="sessions", sessions=sessions_list())

@app.route("/sessions/<int:sid>")
def session_detail(sid):
    data = session_get(sid)
    if not data:
        return "Session not found", 404
    return render_template("session_detail.html", active="sessions", data=data)

@app.route("/connect")
def connect():
    if os.environ.get("RENDER"):
        base = f"{request.scheme}://{request.host}"
        return render_template("connect.html", active="connect",
                               ip=request.host, sender_url=f"{base}/sender")
    ip = local_ip()
    return render_template("connect.html", active="connect", ip=ip,
                           sender_url=f"http://{ip}:8000/sender")

@app.route("/sender")
def sender():
    if os.environ.get("RENDER"):
        server_url = f"{request.scheme}://{request.host}"
    else:
        server_url = f"http://{local_ip()}:8000"
    return render_template("sender.html", server_url=server_url)


# ── Session API ────────────────────────────────────────────
@app.route("/api/session/start", methods=["POST"])
def api_session_start():
    data       = request.get_json(silent=True) or {}
    feature    = data.get("feature", "general")
    started_at = data.get("started_at")
    sid        = session_create(feature, started_at)
    return jsonify({"session_id": sid})

@app.route("/api/session/end", methods=["POST"])
def api_session_end():
    data      = request.get_json(silent=True) or {}
    sid       = data.get("session_id")
    readings  = data.get("readings", [])
    ended_at  = data.get("ended_at")
    if sid:
        session_end(sid, readings, ended_at)
    return jsonify({"status": "saved"})

@app.route("/api/sessions")
def api_sessions():
    return jsonify(sessions_list())

@app.route("/api/sessions/<int:sid>")
def api_session(sid):
    data = session_get(sid)
    if not data:
        return jsonify({"error": "not found"}), 404
    return jsonify(data)


# ── SocketIO ───────────────────────────────────────────────
@socketio.on("connect")
def on_connect():
    print("Client connected")

@socketio.on("phone_imu")
def handle_phone_imu(data):
    yaw   = data.get("yaw",   0)
    pitch = data.get("pitch", 0)
    roll  = data.get("roll",  0)
    print(f"  YAW {yaw:>8.2f}  PITCH {pitch:>8.2f}  ROLL {roll:>8.2f}")
    emit("imu", data, broadcast=True)


# ── HTTP data (Sensor Logger / fetch fallback) ─────────────
@app.route("/data", methods=["POST"])
def receive_data():
    body    = request.get_json(silent=True) or {}
    payload = body.get("payload", [])
    for sensor in payload:
        if sensor.get("name") == "orientation":
            v    = sensor.get("values", {})
            data = {"yaw": v.get("yaw", 0), "pitch": v.get("pitch", 0), "roll": v.get("roll", 0)}
            socketio.emit("imu", data)
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    ip = local_ip()
    print(f"\n  Motion Studio")
    print(f"  Dashboard: http://localhost:8000")
    print(f"  Sender:    http://{ip}:8000/sender\n")
    socketio.run(app, host="0.0.0.0", port=8000,
                 use_reloader=False, allow_unsafe_werkzeug=True)

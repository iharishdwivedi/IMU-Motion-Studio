from flask import Flask, request, jsonify, render_template, redirect
from flask_cors import CORS
from database import init_db, session_create, session_end, sessions_list, session_get

app = Flask(__name__)
CORS(app)
init_db()


@app.route("/")
def index():
    return redirect("/sessions")

# ── Feature pages (replay-only on Render) ─────────────────────
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
    return render_template("sessions.html", sessions=sessions_list())

@app.route("/sessions/<int:sid>")
def session_detail(sid):
    data = session_get(sid)
    if not data:
        return "Session not found", 404
    return render_template("session_detail.html", data=data)


# ── Receive API (called by localhost on session end) ───────────
@app.route("/api/session/start", methods=["POST"])
def api_session_start():
    data       = request.get_json(silent=True) or {}
    feature    = data.get("feature", "general")
    started_at = data.get("started_at")
    sid        = session_create(feature, started_at)
    return jsonify({"session_id": sid})

@app.route("/api/session/end", methods=["POST"])
def api_session_end():
    data     = request.get_json(silent=True) or {}
    sid      = data.get("session_id")
    readings = data.get("readings", [])
    ended_at = data.get("ended_at")
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)

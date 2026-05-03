"""Flask backend for the combat sim web playtester.

Run: python app.py  (binds 127.0.0.1:5000)
Single-user local app. Do NOT run multiple sessions concurrently — the combat
module's WEAPON_BONUS / ARMOR_BONUS globals are mutated per session.
"""

from dataclasses import asdict
from flask import Flask, jsonify, render_template, request

from settings_store import load_settings, save_settings, settings_from_form
from web_session import GameSession, Phase

app = Flask(__name__)
session = GameSession()


@app.after_request
def no_cache_static(response):
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.errorhandler(ValueError)
def _bad_request(err):
    return jsonify({"error": str(err)}), 400


@app.errorhandler(PermissionError)
def _conflict(err):
    return jsonify({"error": str(err)}), 409


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "GET":
        return jsonify(asdict(load_settings()))
    payload = request.get_json(force=True, silent=True) or {}
    new_settings = settings_from_form(payload)
    save_settings(new_settings)
    return jsonify(asdict(new_settings))


@app.route("/api/new-game", methods=["POST"])
def api_new_game():
    settings = load_settings()
    session.new_game(settings)
    return jsonify(session.to_visible_dict())


@app.route("/api/state", methods=["GET"])
def api_state():
    return jsonify(session.to_visible_dict())


@app.route("/api/atk-commit", methods=["POST"])
def api_atk_commit():
    payload = request.get_json(force=True, silent=True) or {}
    if payload.get("end_turn"):
        session.submit_atk_commit(end_turn=True)
    else:
        n = payload.get("n")
        if n is None:
            return jsonify({"error": "missing n"}), 400
        session.submit_atk_commit(n=int(n))
    return jsonify(session.to_visible_dict())


@app.route("/api/def-commit", methods=["POST"])
def api_def_commit():
    payload = request.get_json(force=True, silent=True) or {}
    n = payload.get("n")
    if n is None:
        return jsonify({"error": "missing n"}), 400
    session.submit_def_commit(int(n))
    return jsonify(session.to_visible_dict())


@app.route("/api/atk-maneuver", methods=["POST"])
def api_atk_maneuver():
    payload = request.get_json(force=True, silent=True) or {}
    maneuver = payload.get("maneuver")
    if not maneuver:
        return jsonify({"error": "missing maneuver"}), 400
    session.submit_atk_maneuver(
        maneuver=maneuver,
        followup=payload.get("followup"),
        dodge_roll=payload.get("dodge_roll"),
    )
    return jsonify(session.to_visible_dict())


@app.route("/api/def-maneuver", methods=["POST"])
def api_def_maneuver():
    payload = request.get_json(force=True, silent=True) or {}
    maneuver = payload.get("maneuver")
    if not maneuver:
        return jsonify({"error": "missing maneuver"}), 400
    session.submit_def_maneuver(
        maneuver=maneuver,
        dodge_roll=payload.get("dodge_roll"),
    )
    return jsonify(session.to_visible_dict())


@app.route("/api/continue", methods=["POST"])
def api_continue():
    payload = request.get_json(force=True, silent=True) or {}
    cont = payload.get("continue")
    session.submit_continue(cont=cont)
    return jsonify(session.to_visible_dict())


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

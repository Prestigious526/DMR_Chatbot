"""
server.py
---------
Flask REST API for the DMR HHPC Fault Diagnosis chatbot.

Routes:
  GET  /                              -> frontend index.html
  POST /api/session/new               -> create session
  POST /api/session/<id>/message      -> user message
  POST /api/session/<id>/reset        -> reset session
  GET  /api/status                    -> server + LLM health check
"""

from __future__ import annotations
import argparse, os, sys
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from session_manager import SessionManager

_FRONTEND = Path(__file__).parent / ".." / "frontend"

app = Flask(__name__, static_folder=str(_FRONTEND / "static"))
CORS(app)
manager = SessionManager()


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(str(_FRONTEND), "index.html")

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@app.route("/api/status", methods=["GET"])
def status():
    """Health check — also reports LLM availability."""
    llm_info = {"backend": os.getenv("LLM_BACKEND", "ollama"), "available": False}
    try:
        from llm import LLMManager
        llm = LLMManager()
        llm_info = llm.get_backend_info()
    except Exception as e:
        llm_info["error"] = str(e)

    rag_index_exists = (
        Path(__file__).parent / ".." / "data" / "faiss_index" / "index.faiss"
    ).exists()

    return jsonify({
        "status": "ok",
        "tier1": "ready",
        "tier2_llm": llm_info,
        "rag_index": "ready" if rag_index_exists else "not built (run: python rag_engine.py --build)",
    })


@app.route("/api/session/new", methods=["POST"])
def new_session():
    resp = manager.create_session()
    return jsonify(resp.to_dict()), 201


@app.route("/api/session/<session_id>/message", methods=["POST"])
def send_message(session_id: str):
    body = request.get_json(silent=True) or {}
    text = body.get("text", "").strip()
    if not text:
        return jsonify({"error": "'text' field is required."}), 400
    resp = manager.handle_input(session_id, text)
    status = 200 if resp.message_type != "error" else 400
    return jsonify(resp.to_dict()), status


@app.route("/api/session/<session_id>/reset", methods=["POST"])
def reset_session(session_id: str):
    resp = manager.reset_session(session_id)
    return jsonify(resp.to_dict())


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found."}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error.", "detail": str(e)}), 500


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port",  type=int, default=5000)
    parser.add_argument("--host",  default="127.0.0.1")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    print(f"\n  DMR HHPC Fault Diagnosis Server")
    print(f"  http://{args.host}:{args.port}\n")
    app.run(host=args.host, port=args.port, debug=args.debug)

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlencode

from flask import Flask, abort, make_response, redirect, request, send_from_directory


BASE_DIR = Path(__file__).resolve().parent
TOKEN = os.environ.get("APP_TOKEN", "")
COOKIE_NAME = "a2t_auth"

app = Flask(__name__)


def _is_authorized() -> bool:
    if not TOKEN:
        return True

    query_token = request.args.get("token", "")
    cookie_token = request.cookies.get(COOKIE_NAME, "")
    return query_token == TOKEN or cookie_token == TOKEN


@app.before_request
def check_auth() -> None:
    if request.path == "/healthz":
        return

    if _is_authorized():
        return

    abort(401)


@app.after_request
def set_auth_cookie(response):
    query_token = request.args.get("token", "")
    if TOKEN and query_token == TOKEN:
        response.set_cookie(
            COOKIE_NAME,
            TOKEN,
            httponly=True,
            secure=True,
            samesite="Lax",
            max_age=60 * 60 * 12,
        )
    return response


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.route("/", defaults={"req_path": "index.html"})
@app.route("/<path:req_path>")
def serve(req_path: str):
    target = BASE_DIR / req_path

    if target.is_dir():
        target = target / "index.html"

    if not target.exists() or not target.is_file():
        abort(404)

    return send_from_directory(BASE_DIR, str(target.relative_to(BASE_DIR)))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)

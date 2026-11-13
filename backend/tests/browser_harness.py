"""Explicitly launched local browser checks. Never imported by app.main or mounted in production.

Run from backend/: .venv/bin/uvicorn browser_harness:app --app-dir tests --host 127.0.0.1
Use --port 8000 with the existing HTTPS Next.js proxy. Requires TEST_DATABASE_URL.
"""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import Request, Response
from pydantic import BaseModel
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from starlette.responses import HTMLResponse

from app.config import Settings
from app.main import create_app
from app.models import VisitorContext
from app.visitor_sessions import (
    COOKIE_NAME,
    CurrentVisitor,
    clear_session_cookie,
    get_clock,
    resolve_visitor,
)

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
test_url = os.environ.get("TEST_DATABASE_URL", "")
if not test_url or not make_url(test_url).database.endswith("_test"):
    raise RuntimeError("Browser harness requires a dedicated TEST_DATABASE_URL ending in _test")
app = create_app(Settings(database_url=test_url))
offset = timedelta()


def now():
    return datetime.now(UTC) + offset


app.dependency_overrides[get_clock] = lambda: now


@app.get("/api/v1/_session-tests/current")
def current(visitor: CurrentVisitor):
    return visitor


class Control(BaseModel):
    operation: Literal["clear", "invalid", "invalidate", "advance"]


@app.post("/api/v1/_session-tests/control")
def control(payload: Control, request: Request, response: Response):
    global offset
    if payload.operation == "clear":
        clear_session_cookie(response)
    elif payload.operation == "invalid":
        # A public noncredential used solely to exercise browser rejection/clearing.
        response.set_cookie(
            COOKIE_NAME, "A" * 43, path="/", secure=True, httponly=True, samesite="lax"
        )
    elif payload.operation == "invalidate":
        visitor = resolve_visitor(request, now)
        with Session(request.app.state.engine) as db, db.begin():
            db.get(VisitorContext, visitor.visitor_context_id).invalidated_at = now()
    else:
        # Server-only test clock; cookie remains unexpired in the real browser.
        offset += timedelta(hours=25)
    return {"ok": True}


@app.get("/api/v1/_session-tests")
def page():
    return HTMLResponse(PAGE)


PAGE = Path(__file__).with_name("session_checks.html").read_text(encoding="utf-8")

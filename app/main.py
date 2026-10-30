from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import decks, srs
from .db import connect
from .modes import MODES

STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Svenska")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

_conn = None


def get_conn():
    global _conn
    if _conn is None:
        _conn = connect()
    return _conn


class Answer(BaseModel):
    item_id: str
    answers: dict[str, str] = {}
    params: dict[str, str] = {}


class ItemRef(BaseModel):
    item_id: str
    params: dict[str, str] = {}


def get_mode(name):
    mode = MODES.get(name)
    if mode is None:
        raise HTTPException(404, f"unknown mode {name}")
    return mode


def get_item(mode, conn, item_id):
    item = mode.get(conn, item_id)
    if item is None:
        raise HTTPException(404, f"unknown item {item_id}")
    return item


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/{mode_name}/next")
def next_card(mode_name: str, request: Request, conn=Depends(get_conn)):
    mode = get_mode(mode_name)
    params = dict(request.query_params)
    key = mode.key(params)
    ordered = mode.ordered_ids(conn, params)
    item_id, kind = srs.pick_next(conn, key, ordered, mode.active_size)
    summary = srs.mode_summary(conn, key, ordered)
    if item_id is None:
        return {"done": True, "summary": summary}
    item = get_item(mode, conn, item_id)
    return {
        "done": False,
        "item_id": item_id,
        "kind": kind,
        "card": mode.card(item, params),
        "status": srs.item_status(conn, key, item_id),
        "summary": summary,
    }


@app.post("/api/{mode_name}/answer")
def answer(mode_name: str, body: Answer, conn=Depends(get_conn)):
    mode = get_mode(mode_name)
    item = get_item(mode, conn, body.item_id)
    fields = mode.grade(item, body.answers)
    status = srs.record_attempt(conn, mode.key(body.params), body.item_id, fields, mode.learn_streak)
    return {"fields": fields, "all_correct": all(f["correct"] for f in fields.values()), "status": status}


@app.post("/api/{mode_name}/override")
def override(mode_name: str, body: ItemRef, conn=Depends(get_conn)):
    mode = get_mode(mode_name)
    return {"status": srs.override_last(conn, mode.key(body.params), body.item_id, mode.learn_streak)}


@app.post("/api/{mode_name}/known")
def mark_known(mode_name: str, body: ItemRef, conn=Depends(get_conn)):
    mode = get_mode(mode_name)
    return {"status": srs.set_flag(conn, mode.key(body.params), body.item_id, learned=True)}


@app.post("/api/{mode_name}/relearn")
def relearn(mode_name: str, body: ItemRef, conn=Depends(get_conn)):
    mode = get_mode(mode_name)
    return {"status": srs.set_flag(conn, mode.key(body.params), body.item_id, learned=False, excluded=False)}


@app.post("/api/{mode_name}/exclude")
def exclude(mode_name: str, body: ItemRef, conn=Depends(get_conn)):
    mode = get_mode(mode_name)
    return {"status": srs.set_flag(conn, mode.key(body.params), body.item_id, excluded=True)}


@app.get("/api/{mode_name}/stats")
def stats(mode_name: str, request: Request, conn=Depends(get_conn)):
    mode = get_mode(mode_name)
    params = dict(request.query_params)
    key = mode.key(params)
    ordered = mode.ordered_ids(conn, params)
    rows = srs.item_table(conn, key, ordered)
    for r in rows:
        item = mode.get(conn, r["item_id"])
        r["label"] = mode.label(item) if item else r["item_id"]
    return {"summary": srs.mode_summary(conn, key, ordered), "items": rows}


@app.get("/api/decks")
def get_decks(conn=Depends(get_conn)):
    return decks.list_decks(conn)


@app.post("/api/decks")
async def upload_deck(file: UploadFile = File(...), name: str = Form(""), conn=Depends(get_conn)):
    pairs = decks.parse_csv(await file.read())
    if not pairs:
        raise HTTPException(400, "No Swedish/English pairs found. Use two columns: swedish,english")
    deck_name = name.strip() or Path(file.filename or "deck").stem
    deck_id = decks.create_deck(conn, deck_name, pairs)
    return {"id": deck_id, "name": deck_name, "size": len(pairs)}


@app.delete("/api/decks/{deck_id}")
def remove_deck(deck_id: int, conn=Depends(get_conn)):
    decks.delete_deck(conn, deck_id)
    return {"ok": True}

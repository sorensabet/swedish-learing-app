import importlib

import pytest
from fastapi.testclient import TestClient

from app import grading, srs
from app.db import connect
from app.decks import parse_csv
from app.modes import MODES


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SWEDISH_APP_DB", str(tmp_path / "test.db"))
    import app.main as main
    importlib.reload(main)
    return TestClient(main.app)


def test_english_matching():
    glosses = ["run", "go, ride, drive", "(automobile)", "am/are/is"]
    for answer in ["run", "to run", "Drive", "automobile", "is"]:
        assert grading.check_english(answer, glosses)
    assert not grading.check_english("walk", glosses)
    assert not grading.check_english("", glosses)


def test_swedish_matching():
    assert grading.check_swedish("bil", "en bil")
    assert grading.check_swedish("en bil", "bil")
    assert grading.check_swedish("springa", "att springa; löpa")
    assert grading.check_swedish("löpa", "att springa; löpa")
    assert not grading.check_swedish("bilen", "en bil")


def test_noun_grading():
    mode = MODES["nouns"]
    bil = next(n for n in mode.items if n["lemma"] == "bil")
    fields = mode.grade(bil, {"gender": "en", "def_sg": "bilen", "indef_pl": "bilar", "def_pl": "bilarna"})
    assert all(f["correct"] for f in fields.values())
    fields = mode.grade(bil, {"gender": "ett", "def_sg": "bilet", "indef_pl": "bilar", "def_pl": "bilarna"})
    assert not fields["gender"]["correct"] and not fields["def_sg"]["correct"] and fields["def_pl"]["correct"]


def test_verb_data_and_groups():
    mode = MODES["verbs"]
    by_lemma = {}
    for v in mode.items:
        by_lemma.setdefault(v["lemma"], v)
    expected = {"tala": "1", "prata": "1", "köpa": "2b", "ringa": "2a", "bo": "3", "tro": "3", "skriva": "4", "vara": "4"}
    for lemma, group in expected.items():
        if lemma in by_lemma:
            assert by_lemma[lemma]["group"] == group, lemma
    springa = by_lemma["springa"]
    assert (springa["imperative"], springa["present"], springa["preterite"], springa["supine"]) == (
        "spring", "springer", "sprang", "sprungit"
    )
    fields = mode.grade(springa, {
        "translation": "to run", "imperative": "spring", "infinitive": "springa", "present": "springer",
        "preterite": "sprang", "supine": "sprungit", "group": "4",
    })
    assert all(f["correct"] for f in fields.values())


def test_group_two_accepts_plain_two():
    mode = MODES["verbs"]
    kopa = next(v for v in mode.items if v["lemma"] == "köpa")
    assert mode.grade(kopa, {"group": "2"})["group"]["correct"]
    assert mode.grade(kopa, {"group": "2b"})["group"]["correct"]
    assert not mode.grade(kopa, {"group": "2a"})["group"]["correct"]


def test_frequency_order_is_sensible():
    nouns = [n["lemma"] for n in MODES["nouns"].items[:50]]
    for word in ["år", "dag", "barn", "tid"]:
        assert word in nouns
    for junk in ["jag", "men", "med", "en"]:
        assert junk not in nouns
    verbs = [v["lemma"] for v in MODES["verbs"].items[:20]]
    for word in ["vara", "ha", "göra", "komma"]:
        assert word in verbs


def test_cloze_blanks_match_text():
    for item in MODES["cloze"].items:
        for b in item["blanks"]:
            assert item["text"][b["start"]:b["end"]] == b["form"]


def test_scheduler_introduces_new_then_reviews(tmp_path):
    conn = connect(tmp_path / "s.db")
    ids = [f"w{i}" for i in range(10)]
    first, kind = srs.pick_next(conn, "m", ids, active_size=2)
    assert (first, kind) == ("w0", "new")
    wrong = {"f": {"correct": False}}
    right = {"f": {"correct": True}}
    srs.record_attempt(conn, "m", "w0", wrong, learn_streak=2)
    assert srs.pick_next(conn, "m", ids, active_size=2) == ("w1", "new")
    srs.record_attempt(conn, "m", "w1", right, learn_streak=2)
    assert srs.item_status(conn, "m", "w1")["learned"]
    assert srs.pick_next(conn, "m", ids, active_size=2) == ("w2", "new")
    srs.record_attempt(conn, "m", "w2", wrong, learn_streak=2)
    item, kind = srs.pick_next(conn, "m", ids, active_size=2)
    assert kind == "review" and item in {"w0", "w2"}
    srs.record_attempt(conn, "m", "w0", right, learn_streak=2)
    srs.record_attempt(conn, "m", "w0", right, learn_streak=2)
    assert srs.item_status(conn, "m", "w0")["learned"]


def test_override_counts_as_correct(tmp_path):
    conn = connect(tmp_path / "o.db")
    srs.record_attempt(conn, "m", "x", {"a": {"correct": False}}, learn_streak=3)
    status = srs.override_last(conn, "m", "x", learn_streak=3)
    assert status["correct"] == 1 and status["learned"]


def test_parse_csv_variants():
    assert parse_csv(b"swedish,english\nhund,dog\nkatt,cat\n") == [("hund", "dog"), ("katt", "cat")]
    assert parse_csv("english;svenska\ndog;hund\n") == [("hund", "dog")]
    assert parse_csv("hund\tdog\nhund\tdog\n") == [("hund", "dog")]


def test_api_flow(client):
    nxt = client.get("/api/nouns/next").json()
    assert nxt["kind"] == "new" and nxt["card"]["word"]
    res = client.post("/api/nouns/answer", json={"item_id": nxt["item_id"], "answers": {"gender": "en"}}).json()
    assert "gender" in res["fields"]
    assert client.get("/api/nouns/stats").json()["summary"]["seen"] == 1

    up = client.post("/api/decks", files={"file": ("words.csv", b"swedish,english\nhund,dog\n")}, data={"name": "Djur"})
    deck = up.json()["id"]
    card = client.get(f"/api/translate/next?deck={deck}&direction=sv2en").json()
    assert card["card"]["word"] == "hund"
    graded = client.post(
        "/api/translate/answer",
        json={"item_id": card["item_id"], "answers": {"answer": "a dog"}, "params": {"deck": str(deck)}},
    ).json()
    assert graded["all_correct"]
    done = client.get(f"/api/translate/next?deck={deck}&direction=sv2en").json()
    assert done["done"]
    card = client.get(f"/api/translate/next?deck={deck}&direction=en2sv").json()
    assert card["card"]["word"] == "dog"

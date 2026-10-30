import json
import random
import time


def smoothed_accuracy(row):
    return (row["correct"] + 1) / (row["attempts"] + 2)


def progress_rows(conn, mode):
    return {r["item_id"]: r for r in conn.execute("SELECT * FROM progress WHERE mode = ?", (mode,))}


def pick_next(conn, mode, ordered_ids, active_size, rng=random):
    rows = progress_rows(conn, mode)
    active = [
        i for i in ordered_ids
        if i in rows and rows[i]["attempts"] > 0 and not rows[i]["learned"] and not rows[i]["excluded"]
    ]
    if len(active) < active_size:
        for item_id in ordered_ids:
            row = rows.get(item_id)
            if row is None or (row["attempts"] == 0 and not row["learned"] and not row["excluded"]):
                return item_id, "new"
    if not active:
        return None, None
    recent = sorted(active, key=lambda i: rows[i]["last_seen"] or 0, reverse=True)[: min(2, len(active) - 1)]
    candidates = [i for i in active if i not in recent]
    weights = [1.2 - smoothed_accuracy(rows[i]) for i in candidates]
    return rng.choices(candidates, weights=weights)[0], "review"


def _ensure_row(conn, mode, item_id):
    conn.execute("INSERT OR IGNORE INTO progress (mode, item_id) VALUES (?, ?)", (mode, item_id))
    return conn.execute("SELECT * FROM progress WHERE mode = ? AND item_id = ?", (mode, item_id)).fetchone()


def _merge_fields(field_stats, fields):
    for name, res in fields.items():
        c, n = field_stats.get(name, [0, 0])
        field_stats[name] = [c + int(res["correct"]), n + 1]
    return field_stats


def _is_learned(all_correct, attempt_no, streak, learn_streak):
    return all_correct and (attempt_no == 1 or streak >= learn_streak)


def record_attempt(conn, mode, item_id, fields, learn_streak):
    row = _ensure_row(conn, mode, item_id)
    all_correct = all(r["correct"] for r in fields.values())
    score = sum(r["correct"] for r in fields.values()) / max(len(fields), 1)
    attempt_no = row["attempts"] + 1
    streak = row["streak"] + 1 if all_correct else 0
    learned = int(row["learned"] or _is_learned(all_correct, attempt_no, streak, learn_streak))
    field_stats = _merge_fields(json.loads(row["field_stats"]), fields)
    now = time.time()
    conn.execute(
        """UPDATE progress SET attempts = ?, correct = correct + ?, streak = ?, learned = ?,
           last_seen = ?, field_stats = ? WHERE mode = ? AND item_id = ?""",
        (attempt_no, int(all_correct), streak, learned, now, json.dumps(field_stats), mode, item_id),
    )
    conn.execute(
        """INSERT INTO attempts (mode, item_id, ts, all_correct, score, details, streak_before, attempt_no)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (mode, item_id, now, int(all_correct), score, json.dumps(fields, ensure_ascii=False), row["streak"], attempt_no),
    )
    conn.commit()
    return item_status(conn, mode, item_id)


def override_last(conn, mode, item_id, learn_streak):
    last = conn.execute(
        "SELECT * FROM attempts WHERE mode = ? AND item_id = ? ORDER BY id DESC LIMIT 1", (mode, item_id)
    ).fetchone()
    if last is None or last["all_correct"]:
        return item_status(conn, mode, item_id)
    row = _ensure_row(conn, mode, item_id)
    fields = json.loads(last["details"])
    field_stats = json.loads(row["field_stats"])
    for name, res in fields.items():
        if not res["correct"] and name in field_stats:
            field_stats[name][0] += 1
        res["correct"] = True
    streak = last["streak_before"] + 1
    learned = int(row["learned"] or _is_learned(True, last["attempt_no"], streak, learn_streak))
    conn.execute(
        "UPDATE progress SET correct = correct + 1, streak = ?, learned = ?, field_stats = ? WHERE mode = ? AND item_id = ?",
        (streak, learned, json.dumps(field_stats), mode, item_id),
    )
    conn.execute(
        "UPDATE attempts SET all_correct = 1, score = 1, overridden = 1, details = ? WHERE id = ?",
        (json.dumps(fields, ensure_ascii=False), last["id"]),
    )
    conn.commit()
    return item_status(conn, mode, item_id)


def set_flag(conn, mode, item_id, **flags):
    _ensure_row(conn, mode, item_id)
    for name, value in flags.items():
        if name not in ("learned", "excluded"):
            raise ValueError(name)
        conn.execute(f"UPDATE progress SET {name} = ? WHERE mode = ? AND item_id = ?", (int(value), mode, item_id))
    if flags.get("learned") is False:
        conn.execute("UPDATE progress SET streak = 0 WHERE mode = ? AND item_id = ?", (mode, item_id))
    conn.commit()
    return item_status(conn, mode, item_id)


def item_status(conn, mode, item_id):
    row = conn.execute("SELECT * FROM progress WHERE mode = ? AND item_id = ?", (mode, item_id)).fetchone()
    if row is None:
        return {"attempts": 0, "correct": 0, "streak": 0, "learned": False, "accuracy": None, "fields": {}}
    return {
        "attempts": row["attempts"],
        "correct": row["correct"],
        "streak": row["streak"],
        "learned": bool(row["learned"]),
        "excluded": bool(row["excluded"]),
        "accuracy": row["correct"] / row["attempts"] if row["attempts"] else None,
        "fields": {k: v[0] / v[1] for k, v in json.loads(row["field_stats"]).items() if v[1]},
    }


def mode_summary(conn, mode, ordered_ids):
    rows = progress_rows(conn, mode)
    ids = set(ordered_ids)
    seen = [r for i, r in rows.items() if i in ids and r["attempts"] > 0]
    attempts = sum(r["attempts"] for r in seen)
    correct = sum(r["correct"] for r in seen)
    return {
        "total": len(ordered_ids),
        "seen": len(seen),
        "learned": sum(1 for i, r in rows.items() if i in ids and r["learned"]),
        "in_progress": sum(1 for r in seen if not r["learned"] and not r["excluded"]),
        "excluded": sum(1 for i, r in rows.items() if i in ids and r["excluded"]),
        "attempts": attempts,
        "accuracy": correct / attempts if attempts else None,
    }


def item_table(conn, mode, ordered_ids):
    rows = progress_rows(conn, mode)
    out = []
    for rank, item_id in enumerate(ordered_ids, 1):
        r = rows.get(item_id)
        if r is None or (r["attempts"] == 0 and not r["learned"] and not r["excluded"]):
            continue
        status = "excluded" if r["excluded"] else "learned" if r["learned"] else "learning"
        out.append({"item_id": item_id, "rank": rank, "status": status, **item_status(conn, mode, item_id)})
    return out

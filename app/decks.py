import csv
import io
import time

SV_HEADERS = {"swedish", "svenska", "sv", "swe", "svensk"}
EN_HEADERS = {"english", "engelska", "en", "eng"}


def parse_csv(raw):
    text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    if not rows:
        return []
    sv_col, en_col = 0, 1
    header = [c.lower() for c in rows[0]]
    if set(header) & SV_HEADERS and set(header) & EN_HEADERS:
        sv_col = next(i for i, c in enumerate(header) if c in SV_HEADERS)
        en_col = next(i for i, c in enumerate(header) if c in EN_HEADERS)
        rows = rows[1:]
    pairs, seen = [], set()
    for r in rows:
        if len(r) <= max(sv_col, en_col):
            continue
        pair = (r[sv_col], r[en_col])
        if pair[0] and pair[1] and pair not in seen:
            seen.add(pair)
            pairs.append(pair)
    return pairs


def create_deck(conn, name, pairs):
    cur = conn.execute("INSERT INTO decks (name, created) VALUES (?, ?)", (name, time.time()))
    deck_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO deck_pairs (deck_id, position, sv, en) VALUES (?, ?, ?, ?)",
        [(deck_id, i, sv, en) for i, (sv, en) in enumerate(pairs)],
    )
    conn.commit()
    return deck_id


def list_decks(conn):
    rows = conn.execute(
        """SELECT d.id, d.name, d.created, COUNT(p.id) AS size
           FROM decks d LEFT JOIN deck_pairs p ON p.deck_id = d.id
           GROUP BY d.id ORDER BY d.created DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def delete_deck(conn, deck_id):
    conn.execute("DELETE FROM deck_pairs WHERE deck_id = ?", (deck_id,))
    conn.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
    conn.execute("DELETE FROM progress WHERE mode = ?", (f"translate:{deck_id}",))
    conn.execute("DELETE FROM attempts WHERE mode = ?", (f"translate:{deck_id}",))
    conn.commit()

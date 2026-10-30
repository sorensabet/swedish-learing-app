import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "cloze_source"
UNIMORPH = ROOT / "data" / "raw" / "unimorph_swe.tsv"


def load_adjective_tables(path):
    tables = defaultdict(set)
    if not path.exists():
        return tables
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 3 and parts[2].startswith("ADJ"):
                tables[parts[0]].add(parts[1].lower())
    return tables


def find_span(text, form, occurrence):
    matches = list(re.finditer(rf"(?<!\w){re.escape(form)}(?!\w)", text))
    if len(matches) < occurrence:
        return None
    m = matches[occurrence - 1]
    return m.start(), m.end()


def validate(paragraph, tags, adjectives):
    blanks, problems, used = [], [], set()
    for t in tags:
        form, base, pos = t.get("form", ""), t.get("base", "").strip(), t.get("pos")
        span = find_span(paragraph["text"], form, int(t.get("occurrence") or 1))
        if span is None:
            problems.append(f"{form!r} not found")
            continue
        if span in used:
            continue
        if pos not in ("ADJ", "ADV") or not base:
            problems.append(f"{form!r} bad pos/base")
            continue
        table = adjectives.get(base.lower())
        if table and form.lower() not in table and base.lower() not in {"bra", "mycket", "många", "få"}:
            problems.append(f"{form!r} not an inflection of {base!r}")
            continue
        used.add(span)
        blanks.append({"start": span[0], "end": span[1], "form": form, "base": base, "pos": pos, "rule": t.get("rule", "")})
    blanks.sort(key=lambda b: b["start"])
    return blanks, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-blanks", type=int, default=2)
    args = ap.parse_args()

    paragraphs = json.loads((SOURCE / "paragraphs.json").read_text(encoding="utf-8"))
    tags = {}
    for path in sorted(SOURCE.glob("tags_*.json")):
        for entry in json.loads(path.read_text(encoding="utf-8")):
            tags[entry["id"]] = entry["blanks"]
    adjectives = load_adjective_tables(UNIMORPH)

    items, dropped = [], 0
    for p in paragraphs:
        if p["id"] not in tags:
            print(f"{p['id']}: no tags", file=sys.stderr)
            continue
        blanks, problems = validate(p, tags[p["id"]], adjectives)
        dropped += len(problems)
        for problem in problems:
            print(f"{p['id']}: dropped {problem}", file=sys.stderr)
        if len(blanks) >= args.min_blanks:
            items.append({"id": p["id"], "topic": p["topic"], "text": p["text"], "blanks": blanks})

    random.Random(7).shuffle(items)
    for rank, item in enumerate(items, 1):
        item["rank"] = rank
    out = ROOT / "data" / "cloze.json"
    out.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {len(items)} paragraphs, {sum(len(i['blanks']) for i in items)} blanks, dropped {dropped} to {out}")


if __name__ == "__main__":
    main()

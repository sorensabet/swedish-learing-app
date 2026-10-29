import json
import random
from collections import Counter
from functools import cached_property
from pathlib import Path

from . import grading
from .grading import result

DATA = Path(__file__).resolve().parent.parent / "data"


def load_json(name):
    path = DATA / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


class Mode:
    name = ""
    active_size = 15
    learn_streak = 3

    def key(self, params):
        return self.name

    def ordered_ids(self, conn, params):
        return [i["id"] for i in self.items]

    def get(self, conn, item_id):
        return self.by_id.get(item_id)

    @cached_property
    def items(self):
        return load_json(self.name)

    @cached_property
    def by_id(self):
        return {i["id"]: i for i in self.items}

    def label(self, item):
        return item["lemma"]


class NounMode(Mode):
    name = "nouns"

    def card(self, item, params):
        return {
            "word": item["indef_sg"],
            "translations": item["translations"][:4],
            "rank": item["rank"],
            "has_plural": item["indef_pl"] is not None,
        }

    def grade(self, item, answers):
        alts = item.get("alts", {})
        fields = {"gender": result(answers.get("gender"), item["gender"], grading.norm(answers.get("gender")) == item["gender"])}
        for slot in ("def_sg", "indef_pl", "def_pl"):
            if item[slot] is None:
                continue
            given = answers.get(slot)
            fields[slot] = result(given, item[slot], grading.check_form(given, item[slot], alts.get(slot, [])))
        return fields


VERB_FIELDS = ("translation", "imperative", "infinitive", "present", "preterite", "supine", "group")
PROMPT_SLOTS = ("present", "preterite", "supine")


class VerbMode(Mode):
    name = "verbs"

    @cached_property
    def form_counts(self):
        counts = Counter()
        for v in self.items:
            for f in {v["infinitive"], v["present"], v["preterite"], v["supine"], v["imperative"]} - {None}:
                counts[f] += 1
        return counts

    def prompt(self, item, style):
        if style == "infinitive":
            return item["infinitive"], "infinitive"
        options = [s for s in PROMPT_SLOTS if self.form_counts[item[s]] == 1 and item[s] != item["infinitive"]]
        if not options:
            return item["infinitive"], "infinitive"
        slot = random.choice(options)
        return item[slot], slot

    def card(self, item, params):
        prompt, slot = self.prompt(item, params.get("prompt", "random"))
        return {
            "word": prompt,
            "prompt_slot": slot,
            "rank": item["rank"],
            "has_imperative": item["imperative"] is not None,
            "deponent": item["deponent"],
        }

    def grade(self, item, answers):
        alts = item.get("alts", {})
        fields = {
            "translation": result(
                answers.get("translation"),
                "; ".join(item["translations"][:4]),
                grading.check_english(answers.get("translation"), item["translations"]),
            )
        }
        for slot in ("imperative", "infinitive", "present", "preterite", "supine"):
            if item[slot] is None:
                continue
            given = answers.get(slot)
            fields[slot] = result(given, item[slot], grading.check_form(given, item[slot], alts.get(slot, [])))
        group_given = grading.norm(answers.get("group"))
        fields["group"] = result(answers.get("group"), item["group"], group_given in {item["group"], item["group"][0]})
        return fields


class ClozeMode(Mode):
    name = "cloze"
    active_size = 6
    learn_streak = 2

    def label(self, item):
        return item["topic"]

    def segments(self, item):
        out, pos = [], 0
        for i, b in enumerate(item["blanks"]):
            out.append({"text": item["text"][pos:b["start"]]})
            out.append({"blank": i, "base": b["base"], "pos": b["pos"]})
            pos = b["end"]
        out.append({"text": item["text"][pos:]})
        return out

    def card(self, item, params):
        return {"topic": item["topic"], "segments": self.segments(item), "rank": item["rank"]}

    def grade(self, item, answers):
        fields = {}
        for i, b in enumerate(item["blanks"]):
            given = answers.get(str(i))
            fields[str(i)] = {
                **result(given, b["form"], grading.norm(given) == grading.norm(b["form"])),
                "base": b["base"],
                "rule": b["rule"],
            }
        return fields


DIRECTIONS = ("sv2en", "en2sv")


class TranslateMode(Mode):
    name = "translate"
    active_size = 12
    learn_streak = 3

    def key(self, params):
        return f"translate:{params.get('deck')}"

    def directions(self, params):
        d = params.get("direction", "both")
        return DIRECTIONS if d == "both" else (d,)

    def ordered_ids(self, conn, params):
        rows = conn.execute(
            "SELECT id FROM deck_pairs WHERE deck_id = ? ORDER BY position", (params.get("deck"),)
        ).fetchall()
        return [f"{r['id']}:{d}" for r in rows for d in self.directions(params)]

    def get(self, conn, item_id):
        pair_id, direction = item_id.split(":")
        row = conn.execute("SELECT * FROM deck_pairs WHERE id = ?", (pair_id,)).fetchone()
        if row is None or direction not in DIRECTIONS:
            return None
        return {"id": item_id, "sv": row["sv"], "en": row["en"], "direction": direction, "rank": row["position"] + 1}

    def label(self, item):
        return f"{item['sv']} — {item['en']}"

    def card(self, item, params):
        word = item["sv"] if item["direction"] == "sv2en" else item["en"]
        return {"word": word, "direction": item["direction"], "rank": item["rank"]}

    def grade(self, item, answers):
        given = answers.get("answer")
        if item["direction"] == "sv2en":
            ok = grading.check_english(given, [item["en"]])
            expected = item["en"]
        else:
            ok = grading.check_swedish(given, item["sv"])
            expected = item["sv"]
        return {"answer": result(given, expected, ok)}


MODES = {m.name: m for m in (NounMode(), VerbMode(), ClozeMode(), TranslateMode())}

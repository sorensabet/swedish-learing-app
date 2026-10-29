import argparse
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from wordfreq import word_frequency

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

FOLKETS_URL = (
    "https://raw.githubusercontent.com/dpriskorn/lexfolketslexicon/"
    "d0820ff1477e92962ca9630132cd0c320a76d205/data/folkets_sv_en_public.xml"
)
UNIMORPH_URL = (
    "https://raw.githubusercontent.com/unimorph/swe/"
    "dbd4aef2bb0940277894523708b2341930a94d57/swe"
)

LETTERS = re.compile(r"^[a-zåäöéü]+$")


def fetch(url, path):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {url}")
        urllib.request.urlretrieve(url, path)
    return path


def clean_translation(t):
    t = re.sub(r"\[.*?\]", "", t)
    t = t.replace("&quot;", '"')
    t = re.sub(r"\(\s*\)", "", t)
    t = re.sub(r"\(\s*(.*?)\s*\)", r"(\1)", t)
    return re.sub(r"\s+", " ", t).strip()


def expand_inflection(lemma, form):
    return lemma + form[1:] if form.startswith("-") else form


def load_folkets(path):
    entries = []
    for w in ET.parse(path).getroot().iter("word"):
        lemma = (w.get("value") or "").strip()
        entries.append(
            {
                "lemma": lemma,
                "cls": w.get("class") or "",
                "translations": [
                    clean_translation(t.get("value"))
                    for t in w.findall("translation")
                    if t.get("value")
                ],
                "inflections": [
                    expand_inflection(lemma, i.get("value").strip())
                    for i in w.findall("paradigm/inflection")
                    if i.get("value")
                ],
            }
        )
    return entries


def load_unimorph(path):
    tables = defaultdict(lambda: defaultdict(list))
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3:
                continue
            lemma, form, feats = parts
            pos = feats.split(";")[0]
            tables[(lemma, pos)][feats].append(form)
    return tables


def merge_senses(entries):
    groups = {}
    for e in entries:
        key = (e["lemma"], tuple(e["inflections"]))
        g = groups.setdefault(key, {"lemma": e["lemma"], "inflections": e["inflections"], "translations": []})
        for t in e["translations"]:
            if t and t not in g["translations"]:
                g["translations"].append(t)
    merged = list(groups.values())
    by_lemma = defaultdict(list)
    for g in merged:
        by_lemma[g["lemma"]].append(g)
    out = []
    for lemma, gs in by_lemma.items():
        gs.sort(key=lambda g: -len(g["inflections"]))
        kept = []
        for g in gs:
            parent = next(
                (
                    k
                    for k in kept
                    if g["inflections"]
                    and g["inflections"][0] == k["inflections"][0]
                    and set(g["inflections"]) <= set(k["inflections"])
                ),
                None,
            )
            if parent:
                parent["translations"] += [t for t in g["translations"] if t not in parent["translations"]]
            else:
                kept.append(g)
        out += [g for g in kept if g["translations"]]
    return out


def first(table, feats):
    forms = table.get(feats)
    return forms[0] if forms else None


VERB_ALTS = {
    "säga": {"preterite": ["sa"]},
    "lägga": {"preterite": ["la"]},
    "ge": {"supine": ["givit"], "present": ["giver"]},
    "ta": {"present": ["tager"]},
    "dra": {"present": ["drager"]},
    "bli": {"present": ["bliver"]},
}


def derive_def_pl(indef_pl, lemma, gender):
    if indef_pl.endswith(("are", "ande", "ende")) and gender == "en":
        return indef_pl[:-1] + "na" if indef_pl.endswith("are") else indef_pl + "na"
    if indef_pl.endswith("r"):
        return indef_pl + "na"
    if indef_pl.endswith("n") and gender == "ett" and indef_pl != lemma:
        return indef_pl + "a"
    if indef_pl == lemma and gender == "ett":
        return indef_pl + ("n" if indef_pl.endswith("e") else "en")
    return None


def build_nouns(folkets, unimorph):
    nouns = []
    for g in merge_senses([e for e in folkets if e["cls"] == "nn"]):
        lemma, infl = g["lemma"], g["inflections"]
        if not LETTERS.match(lemma) or not infl:
            continue
        def_sg = infl[0]
        if def_sg.endswith("n"):
            gender = "en"
        elif def_sg.endswith("t"):
            gender = "ett"
        else:
            continue
        indef_pl = def_pl = None
        alts = {}
        source = "folkets"
        um = unimorph.get((lemma, "N"))
        if um and first(um, "N;NOM;SG;DEF") == def_sg and (len(infl) < 2 or first(um, "N;NOM;PL;INDF") == infl[1]):
            indef_pl = first(um, "N;NOM;PL;INDF")
            def_pl = first(um, "N;NOM;PL;DEF")
            source = "unimorph"
        elif len(infl) >= 2:
            indef_pl = infl[1]
            def_pl = infl[2] if len(infl) >= 3 else derive_def_pl(indef_pl, lemma, gender)
            if def_pl is None:
                continue
        nouns.append(
            {
                "lemma": lemma,
                "gender": gender,
                "indef_sg": lemma,
                "def_sg": def_sg,
                "indef_pl": indef_pl,
                "def_pl": def_pl,
                "alts": alts,
                "translations": g["translations"],
                "source": source,
            }
        )
    return nouns


def strip_s(form):
    return form[:-1] if form and form.endswith("s") else form


def verb_group(inf, pres, pret, sup):
    if inf.endswith("s") and pres.endswith("s"):
        inf, pres, pret, sup = map(strip_s, (inf, pres, pret, sup))
    if inf.endswith("a") and pret == inf + "de" and sup == inf + "t":
        return "1"
    if not inf.endswith("a") and pret == inf + "dde" and sup == inf + "tt":
        return "3"
    if inf.endswith("a"):
        stem = inf[:-1]
        prets, sups = set(), set()
        for short in {stem, stem[:-1] if stem.endswith(("mm", "nn")) else stem}:
            prets |= {short + "de", short + "te"}
            sups.add(short + "t")
            if short.endswith(("d", "t")):
                prets.add(short + "e")
            if short.endswith("d"):
                sups |= {short[:-1] + "t", short[:-1] + "tt"}
        if pret in prets and sup in sups and pres in {stem + "er", stem + "r", stem}:
            return "2b" if pret.endswith("te") or (stem.endswith("t") and pret == stem + "e") else "2a"
    return "4"


MODALS = {"kunna", "vilja", "böra", "skola", "måste", "må", "lär", "torde", "behöva"}
EXTRA_TRANSLATIONS = {
    "vara": ["be"],
    "finnas": ["exist", "be"],
    "kunna": ["be able to"],
    "få": ["be allowed to"],
    "heta": ["be called"],
    "bli": ["become"],
}


def derive_imperative(inf, pres, group):
    if inf in MODALS - {"behöva"}:
        return None
    if group in ("1", "3") or not inf.endswith("a"):
        return inf
    if pres.endswith("er"):
        return pres[:-2]
    if pres.endswith("r"):
        return pres[:-1]
    return None


def build_verbs(folkets, unimorph):
    verbs = []
    for g in merge_senses([e for e in folkets if e["cls"] == "vb"]):
        lemma, infl = g["lemma"], g["inflections"]
        if len(infl) not in (4, 5) or not all(LETTERS.match(f) for f in [lemma, *infl]):
            continue
        if len(infl) == 5:
            pret, sup, imp, inf, pres = infl
        else:
            pret, sup, inf, pres = infl
            imp = None
        if inf != lemma:
            if inf.startswith(lemma) and len(lemma) <= 3:
                imp = lemma
            elif lemma in infl:
                imp = None
            else:
                continue
            inf = lemma
        source = "folkets"
        alts = VERB_ALTS.get(lemma, {})
        um = unimorph.get((lemma, "V"))
        if um and first(um, "V;IND;SG;ACT;PST") == pret and first(um, "V;V.CVB;ACT") == sup:
            imp = first(um, "V;IMP;ACT") or imp
            pres = first(um, "V;IND;SG;ACT;PRS") or pres
            source = "unimorph"
        deponent = lemma.endswith("s") and pres.endswith("s")
        group = verb_group(inf, pres, pret, sup)
        if imp is None:
            imp = derive_imperative(inf, pres, group)
        if deponent or lemma in MODALS - {"behöva"}:
            imp = None
        verbs.append(
            {
                "lemma": lemma,
                "translations": g["translations"] + EXTRA_TRANSLATIONS.get(lemma, []),
                "imperative": imp,
                "infinitive": inf,
                "present": pres,
                "preterite": pret,
                "supine": sup,
                "group": group,
                "alts": alts,
                "deponent": deponent,
                "source": source,
            }
        )
    return verbs


NOUN_SLOTS = ("indef_sg", "def_sg", "indef_pl", "def_pl")
VERB_SLOTS = ("infinitive", "present", "preterite", "supine", "imperative")


def form_owners(folkets, nouns, verbs):
    owners = defaultdict(int)
    form_lists = [{e["lemma"], *e["inflections"]} for e in folkets if e["cls"] not in ("nn", "vb")]
    form_lists += [{n[s] for s in NOUN_SLOTS} - {None} for n in nouns]
    form_lists += [{v[s] for s in VERB_SLOTS} - {None} for v in verbs]
    for forms in form_lists:
        for f in forms:
            owners[f] += 1
    return owners


def freq(form):
    return word_frequency(form, "sv", wordlist="large")


def slots_by_form(item, slots):
    out = defaultdict(list)
    for s in slots:
        if item.get(s):
            out[item[s]].append(s)
    return out


def slot_shares(items, slots, owners):
    totals = defaultdict(float)
    n = 0
    for item in items:
        by_form = slots_by_form(item, slots)
        if len(by_form) != len(slots) or any(owners[f] > 1 for f in by_form):
            continue
        total = sum(freq(f) for f in by_form)
        if total < 1e-6:
            continue
        for f, ss in by_form.items():
            totals[ss[0]] += freq(f) / total
        n += 1
    return {s: totals[s] / n for s in slots}


def lemma_frequency(item, slots, owners, shares):
    by_form = slots_by_form(item, slots)
    available = sum(shares[s] for ss in by_form.values() for s in ss)
    unique = {f: ss for f, ss in by_form.items() if owners[f] == 1}
    covered = sum(shares[s] for ss in unique.values() for s in ss) / available
    if unique and covered >= 0.05:
        return sum(freq(f) for f in unique) / covered
    return sum(freq(f) / owners[f] for f in by_form) / 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nouns", type=int, default=5000)
    ap.add_argument("--verbs", type=int, default=2000)
    args = ap.parse_args()

    folkets = load_folkets(fetch(FOLKETS_URL, RAW / "folkets_sv_en_public.xml"))
    unimorph = load_unimorph(fetch(UNIMORPH_URL, RAW / "unimorph_swe.tsv"))
    nouns = build_nouns(folkets, unimorph)
    verbs = build_verbs(folkets, unimorph)
    owners = form_owners(folkets, nouns, verbs)

    for items, slots in ((nouns, NOUN_SLOTS), (verbs, VERB_SLOTS)):
        shares = slot_shares(items, slots, owners)
        print("slot shares", {k: round(v, 3) for k, v in shares.items()})
        for item in items:
            item["freq"] = lemma_frequency(item, slots, owners, shares)

    for name, items, limit in (("nouns", nouns, args.nouns), ("verbs", verbs, args.verbs)):
        items = [i for i in items if i["freq"] > 0]
        items.sort(key=lambda i: -i["freq"])
        items = items[:limit]
        for rank, item in enumerate(items, 1):
            item["rank"] = rank
            if name == "nouns":
                item["id"] = f"{item['lemma']}|{item['def_sg']}|{item['indef_pl'] or ''}"
            else:
                item["id"] = f"{item['lemma']}|{item['preterite']}"
            item["freq"] = round(item["freq"] * 1e6, 3)
        out = ROOT / "data" / f"{name}.json"
        out.write_text(json.dumps(items, ensure_ascii=False, indent=0), encoding="utf-8")
        print(f"wrote {len(items)} {name} to {out}")


if __name__ == "__main__":
    main()

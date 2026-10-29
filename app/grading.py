import re
import unicodedata

EN_PREFIXES = ("to ", "a ", "an ", "the ")
SV_PREFIXES = ("att ", "en ", "ett ")


def norm(text):
    text = unicodedata.normalize("NFC", text or "").strip().lower()
    return re.sub(r"\s+", " ", text)


def strip_prefixes(text, prefixes):
    changed = True
    while changed:
        changed = False
        for p in prefixes:
            if text.startswith(p):
                text = text[len(p):]
                changed = True
    return text


def english_variants(gloss):
    gloss = norm(gloss)
    out = set()
    without_parens = re.sub(r"\(.*?\)", " ", gloss)
    with_parens = gloss.replace("(", "").replace(")", "")
    for base in (without_parens, with_parens):
        for part in re.split(r"[,;/]", base):
            part = strip_prefixes(re.sub(r"\s+", " ", part).strip(" .!?"), EN_PREFIXES)
            if part:
                out.add(part)
    return out


def english_answer_set(glosses):
    accepted = set()
    for g in glosses:
        accepted |= english_variants(g)
    return accepted


def check_english(given, glosses):
    answer = strip_prefixes(norm(given).strip(" .!?"), EN_PREFIXES)
    if not answer:
        return False
    accepted = english_answer_set(glosses)
    return answer in accepted or bool(english_variants(given) & accepted)


def check_form(given, expected, alternatives=()):
    answer = norm(given)
    return bool(answer) and answer in {norm(e) for e in (expected, *alternatives) if e}


def swedish_variants(text):
    out = set()
    for part in re.split(r"[,;/]", norm(text)):
        part = re.sub(r"\(.*?\)", "", part).strip(" .!?")
        if part:
            out.add(part)
            out.add(strip_prefixes(part, SV_PREFIXES))
    return out


def check_swedish(given, expected_text):
    answer = norm(given).strip(" .!?")
    if not answer:
        return False
    accepted = swedish_variants(expected_text)
    return answer in accepted or strip_prefixes(answer, SV_PREFIXES) in accepted


def result(given, expected, correct):
    return {"given": given or "", "expected": expected, "correct": bool(correct)}

"""Pull people's names out of OCR'd cards and documents.

ID cards put the holder's name next to or under a label ("Name", "Name/", "नाम / Name", "To"), and relatives
under "Father's Name", "S/O", "C/O" ... OCR output is noisy ("Mame" for "Name", stray letters after the value,
the same card read twice by different OCR passes), so:
  * labels are matched fuzzily (one wrong letter is fine),
  * the value is the run of Capitalised/UPPER-CASE words on the label line or the next lines,
  * candidates are ranked by how often they recur in the text and how name-like they look.
"""
from __future__ import annotations

import re
from collections import Counter

RELATION = re.compile(r"(?:\b(?:fa[a-z]{0,3}er|mo[a-z]{0,3}er|hus[a-z]{0,4})'?s?\s*n[a-z]{0,3}e?\b|\b(?:s/o|d/o|w/o|c/o|son of|daughter of|wife of)\b|पिता\s*का\s*नाम|पति\s*का\s*नाम|माता\s*का\s*नाम)\s*[:/|.\-]*\s*(?P<rest>.*)$", re.I)  # tolerant of OCR misreads ("Faher's Nae")
LABEL_WORDS = ("name", "naam", "holder", "to")
BOILER = set("""
government india govt republic income tax department permanent account number card unique identification authority aadhaar
aadhar enrolment enrollment date birth dob gender male female address mobile abha health national authority signature sign
father mother husband name issued issue valid expiry nationality passport election commission elector photo identity
account bank branch ifsc pay rupees only the of and to for your my mera meri information help helpline www com in gov
services unit floor plot survey model colony near road pune mumbai delhi chowk lost found please inform return tel fax
""".split())
CAP_RUN = re.compile(r"(?:\b[A-Z][A-Za-z'\-]{1,}\.?\s+){0,3}\b[A-Z][A-Za-z'\-]{1,}\b")


def _edit1(a: str, b: str) -> bool:
    """True if a and b differ by at most one substitution/insertion/deletion."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) <= 1
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


def _label_rest(line: str) -> str | None:
    """If the line carries a (possibly misspelt) 'Name' label, return what follows it; else None."""
    toks = re.split(r"([\s/|:]+)", line)
    for i, tok in enumerate(toks):
        w = tok.lower().strip(".-")
        if w and any(w == lw or (len(lw) >= 4 and _edit1(w, lw)) for lw in LABEL_WORDS):
            if w == "to" and i > 0:  # "To" only counts at the start of an address block
                continue
            return "".join(toks[i + 1:]).strip(" :/|.-")
    return None


def _name_like(words: list[str]) -> bool:
    if not 2 <= len(words) <= 4 and not (len(words) == 1 and len(words[0]) >= 4):
        return False
    if any(w.lower().strip(".") in BOILER for w in words):
        return False
    if sum(len(w) for w in words) < 5:
        return False
    return all(re.search(r"[aeiouyAEIOUY]", w) for w in words if len(w) > 2)


def _candidates(s: str) -> list[str]:
    out = []
    for m in CAP_RUN.finditer(s):
        words = [w.strip(".'-") for w in m.group(0).split() if len(w.strip(".'-")) >= 2]
        # an all-caps line is read as one name; in mixed text keep only the capitalised run
        if _name_like(words):
            out.append(" ".join(w.capitalize() if w.isupper() else w for w in words))
    return out


def extract_names(text: str) -> dict[str, list[str]]:
    """{'holder': [...], 'relatives': [...]} from OCR text (best effort, best first)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    holder: Counter[str] = Counter()
    relatives: Counter[str] = Counter()

    def take(rest: str, i: int, bucket: Counter[str]):
        found = _candidates(rest) if rest else []
        j = i + 1
        while not found and j < len(lines) and j <= i + 2:  # the value is often on the next line
            if RELATION.search(lines[j]) or _label_rest(lines[j]) is not None:
                break
            found = _candidates(lines[j])
            j += 1
        for c in found[:1]:
            bucket[c] += 1

    for i, ln in enumerate(lines):
        rm = RELATION.search(ln)
        if rm:
            take(rm.group("rest"), i, relatives)
            continue
        rest = _label_rest(ln)
        if rest is not None:
            take(rest, i, holder)
        elif i + 1 < len(lines) and RELATION.search(lines[i + 1]) and not holder:
            # PAN-style layout: the holder's name sits right above the father's-name label
            for c in _candidates(ln)[:1]:
                holder[c] += 1

    full = " ".join(text.split()).lower()

    def rank(c: Counter[str]) -> list[str]:
        def support(n: str) -> int:
            return full.count(n.lower()) + c[n]

        def key(n: str):
            words = n.split()
            return (support(n), sum(1 for w in words if len(w) >= 3), sum(len(w) for w in words))
        ordered = sorted(c, key=key, reverse=True)
        # several OCR passes agree on the real name; a one-off misread has less support, so drop it
        return [n for n in ordered if support(n) >= support(ordered[0])] if ordered else []

    rel = rank(relatives)[:3]
    hold = [h for h in rank(holder) if h not in rel][:3]
    return {"holder": hold, "relatives": rel}


def person_tokens(names: dict[str, list[str]]) -> list[str]:
    return sorted({w.lower() for n in names.get("holder", []) + names.get("relatives", []) for w in n.split()})

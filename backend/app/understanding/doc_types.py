"""Document-type registry: what a file *is* (PAN card, Aadhaar, ABHA, passport, invoice, signature, ...).

Everything here is data. Each type lists
  aliases   – how people ask for it (any language); used to understand queries
  cues      – phrases found in its text, with weights
  patterns  – regexes for its ID numbers / fields (optionally validated), with weights
  filename  – words that hint at it in a filename
  visual    – a visual cue from `visual.py` that implies it (e.g. a signature)
A file is classified by summing the evidence; queries are matched through the aliases. To support a new kind of
document, add an entry here or put extra entries in a JSON file and point DOC_TYPES_FILE at it (same shape).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ..config import get_settings


@dataclass
class DocType:
    id: str
    label: str
    category: str = "document"            # id | finance | travel | health | education | legal | personal | media
    aliases: list[str] = field(default_factory=list)
    cues: dict[str, float] = field(default_factory=dict)
    patterns: list[dict] = field(default_factory=list)  # {"regex", "weight", "field"?, "check"?}
    filename: list[str] = field(default_factory=list)
    visual: str | None = None
    min_score: float = 4.0


def _verhoeff_ok(num: str) -> bool:
    """Aadhaar numbers carry a Verhoeff check digit; validating it removes random 12-digit false positives."""
    d = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6], [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
         [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1], [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
         [8, 7, 6, 5, 9, 3, 2, 1, 0, 4], [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]
    p = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2], [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
         [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1], [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]]
    digits = [int(c) for c in re.sub(r"\D", "", num)]
    if len(digits) != 12 or digits[0] in (0, 1):
        return False
    c = 0
    for i, n in enumerate(reversed(digits)):
        c = d[c][p[i % 8][n]]
    return c == 0


CHECKS = {"verhoeff": _verhoeff_ok}

BUILTIN: list[DocType] = [
    # ---------------- identity ----------------
    DocType("pan_card", "PAN card", "id",
            aliases=["pan card", "pan", "pancard", "permanent account number", "e-pan", "epan", "income tax card",
                     "पैन कार्ड", "पैन", "पॅन कार्ड", "பான் கார்டு", "tarjeta pan"],
            cues={"permanent account number": 5, "income tax department": 4, "income tax": 2, "e-permanent": 3, "pan services": 2,
                  "nsdl": 1.5, "utiitsl": 1.5, "govt of india": 1, "father's name": 0.5, "आयकर विभाग": 4, "स्थायी लेखा संख्या": 5},
            patterns=[{"regex": r"\b[A-Z]{3}[ABCFGHLJPTK][A-Z][0-9]{4}[A-Z]\b", "weight": 4, "field": "pan_number"}],
            filename=["pan", "pancard", "epan"]),
    DocType("aadhaar_card", "Aadhaar card", "id",
            aliases=["aadhaar card", "aadhaar", "aadhar", "adhaar", "adhar", "aadhar card", "adhar card", "uid card", "e-aadhaar", "eaadhaar",
                     "आधार कार्ड", "आधार", "ஆதார் அட்டை", "ஆதார்"],
            cues={"aadhaar": 5, "aadhar": 4, "unique identification authority": 5, "uidai": 4, "enrolment no": 2, "enrollment no": 2,
                  "mera aadhaar": 3, "meri pehchan": 3, "vid": 0.5, "government of india": 1, "आधार": 4, "भारतीय विशिष्ट पहचान": 5},
            patterns=[{"regex": r"(?<!\d)[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}(?!\d)", "weight": 4, "field": "aadhaar_number", "check": "verhoeff"},
                      {"regex": r"(?<!\d)[2-9]\d{3}\s\d{4}\s\d{4}(?!\d)", "weight": 1.5}],
            filename=["aadhaar", "aadhar", "adhar", "adhaar", "uidai"]),
    DocType("abha_card", "ABHA health card", "health",
            aliases=["abha card", "abha", "health id", "health card", "ayushman bharat health account", "ndhm card",
                     "आभा कार्ड", "आभा", "हेल्थ कार्ड"],
            cues={"ayushman bharat health account": 6, "abha number": 4, "abha address": 4, "abha": 3, "national health authority": 3,
                  "@abdm": 3, "abdm": 2, "health id": 2, "आयुष्मान भारत स्वास्थ्य खाता": 6},
            patterns=[{"regex": r"(?<!\d)\d{2}-\d{4}-\d{4}-\d{4}(?!\d)", "weight": 4, "field": "abha_number"},
                      {"regex": r"\b[\w.]+@(?:abdm|sbx)\b", "weight": 4, "field": "abha_address"}],
            filename=["abha", "healthid", "ndhm"]),
    DocType("ayushman_card", "Ayushman card (PM-JAY)", "health",
            aliases=["ayushman card", "ayushman bharat card", "pmjay card", "pm-jay", "golden card", "आयुष्मान कार्ड"],
            cues={"pradhan mantri jan arogya": 6, "pm-jay": 4, "pmjay": 4, "ayushman bharat": 2},
            filename=["ayushman", "pmjay"]),
    DocType("voter_id", "Voter ID card", "id",
            aliases=["voter id", "voter card", "voter id card", "election card", "epic card", "elector photo identity card", "मतदाता पहचान पत्र", "वोटर आईडी"],
            cues={"election commission of india": 6, "elector": 3, "electors photo identity card": 6, "epic": 2, "निर्वाचन आयोग": 6},
            patterns=[{"regex": r"\b[A-Z]{3}[0-9]{7}\b", "weight": 2.5, "field": "epic_number"}],
            filename=["voter", "epic", "election"]),
    DocType("passport", "Passport", "id",
            aliases=["passport", "पासपोर्ट", "pasaporte", "கடவுச்சீட்டு"],
            cues={"republic of india": 3, "passport no": 4, "passport": 3, "nationality": 1.5, "place of issue": 2, "date of expiry": 1.5,
                  "ministry of external affairs": 3},
            patterns=[{"regex": r"P<[A-Z]{3}[A-Z<]{5,}", "weight": 6, "field": "mrz"},
                      {"regex": r"\b[A-PR-WY][1-9]\d\s?\d{4}[1-9]\b", "weight": 1.5, "field": "passport_number"}],
            filename=["passport"]),
    DocType("driving_licence", "Driving licence", "id",
            aliases=["driving licence", "driving license", "driver license", "driver's license", "dl", "licence", "license", "ड्राइविंग लाइसेंस", "लाइसेंस"],
            cues={"driving licence": 5, "driving license": 5, "transport department": 3, "union of india": 1, "dl no": 3, "licence no": 3,
                  "valid till": 1, "cov": 1, "lmv": 2, "mcwg": 2},
            patterns=[{"regex": r"\b[A-Z]{2}[-\s]?\d{2}[-\s]?(?:19|20)\d{2}\d{7}\b", "weight": 4, "field": "dl_number"}],
            filename=["licence", "license", "dl"]),
    DocType("ration_card", "Ration card", "id",
            aliases=["ration card", "राशन कार्ड", "शिधापत्रिका"],
            cues={"ration card": 6, "public distribution": 3, "food and civil supplies": 4, "fair price shop": 3}, filename=["ration"]),
    # ---------------- personal ----------------
    DocType("signature", "Signature", "personal",
            aliases=["signature", "sign", "my sign", "autograph", "e-signature", "esign", "हस्ताक्षर", "सही", "கையொப்பம்", "firma"],
            cues={"signature": 1.5, "signed": 0.5}, filename=["signature", "sign", "sig", "autograph"], visual="signature", min_score=3.0),
    DocType("birth_certificate", "Birth certificate", "personal",
            aliases=["birth certificate", "जन्म प्रमाण पत्र", "जन्म प्रमाणपत्र"],
            cues={"certificate of birth": 6, "birth certificate": 6, "registration of births": 4, "date of birth": 1, "place of birth": 2},
            filename=["birth"]),
    DocType("marriage_certificate", "Marriage certificate", "personal",
            aliases=["marriage certificate", "विवाह प्रमाण पत्र"], cues={"marriage certificate": 6, "certificate of marriage": 6, "solemnized": 3},
            filename=["marriage"]),
    DocType("vaccination_certificate", "Vaccination certificate", "health",
            aliases=["vaccination certificate", "vaccine certificate", "covid certificate", "cowin certificate"],
            cues={"certificate for covid-19 vaccination": 6, "cowin": 4, "vaccination": 3, "dose": 1, "beneficiary": 1.5}, filename=["vaccin", "cowin"]),
    DocType("medical_report", "Medical report / prescription", "health",
            aliases=["medical report", "lab report", "blood report", "test report", "prescription", "medical record", "रिपोर्ट", "पर्चा"],
            cues={"patient": 2, "diagnosis": 2, "prescription": 3, "rx": 1, "haemoglobin": 3, "hemoglobin": 3, "reference range": 3,
                  "pathology": 3, "specimen": 2, "dr.": 0.5, "mg": 0.5}, filename=["report", "prescription", "lab"]),
    DocType("insurance_policy", "Insurance policy", "finance",
            aliases=["insurance", "insurance policy", "policy document", "health insurance", "car insurance", "बीमा", "पॉलिसी"],
            cues={"policy number": 4, "policy no": 4, "insured": 2, "premium": 2, "sum insured": 4, "insurance": 2, "nominee": 1.5},
            filename=["policy", "insurance"]),
    # ---------------- finance ----------------
    DocType("bank_statement", "Bank statement / passbook", "finance",
            aliases=["bank statement", "passbook", "account statement", "बैंक स्टेटमेंट", "पासबुक"],
            cues={"ifsc": 3, "account statement": 5, "statement of account": 5, "opening balance": 3, "closing balance": 3, "passbook": 4,
                  "withdrawal": 1, "deposit": 0.5, "a/c no": 2, "account no": 1.5}, filename=["statement", "passbook", "bank"]),
    DocType("cheque", "Cheque", "finance",
            aliases=["cheque", "cancelled cheque", "चेक"],
            cues={"pay": 0.5, "or bearer": 4, "rupees": 1, "ifsc": 1.5, "a/c no": 1, "please sign above": 4}, filename=["cheque"]),
    DocType("invoice", "Invoice / bill / receipt", "finance",
            aliases=["invoice", "bill", "receipt", "tax invoice", "electricity bill", "phone bill", "बिल", "रसीद", "factura", "recibo"],
            cues={"tax invoice": 5, "invoice": 3, "invoice no": 4, "bill no": 3, "receipt": 3, "gstin": 3, "amount due": 2, "total": 0.5,
                  "subtotal": 2, "cgst": 2, "sgst": 2, "hsn": 2}, filename=["invoice", "bill", "receipt"]),
    DocType("salary_slip", "Salary slip", "finance",
            aliases=["salary slip", "payslip", "pay slip", "salary statement", "वेतन पर्ची"],
            cues={"payslip": 5, "pay slip": 5, "salary slip": 5, "net pay": 3, "gross earnings": 3, "deductions": 2, "basic": 1, "hra": 2},
            filename=["payslip", "salary"]),
    DocType("tax_return", "Income-tax return / Form 16", "finance",
            aliases=["itr", "income tax return", "form 16", "itr acknowledgement", "tax return"],
            cues={"form 16": 5, "itr-v": 5, "acknowledgement": 1.5, "assessment year": 4, "income tax return": 5, "tds": 2},
            filename=["itr", "form16"]),
    # ---------------- travel ----------------
    DocType("boarding_pass", "Boarding pass / flight ticket", "travel",
            aliases=["boarding pass", "flight ticket", "air ticket", "e-ticket", "plane ticket", "बोर्डिंग पास"],
            cues={"boarding pass": 6, "gate": 1, "seat": 1, "flight": 2, "pnr": 2, "departure": 1, "e-ticket": 2}, filename=["boarding", "flight"]),
    DocType("train_ticket", "Train ticket", "travel",
            aliases=["train ticket", "railway ticket", "irctc ticket", "ट्रेन टिकट"],
            cues={"irctc": 5, "electronic reservation slip": 6, "pnr": 2, "coach": 1, "berth": 2, "train no": 3}, filename=["irctc", "train"]),
    DocType("visa", "Visa", "travel", aliases=["visa"], cues={"visa": 3, "type of visa": 4, "entries": 1.5, "valid from": 1}, filename=["visa"]),
    # ---------------- education / work ----------------
    DocType("marksheet", "Marksheet / transcript", "education",
            aliases=["marksheet", "mark sheet", "marks card", "transcript", "exam result", "मार्कशीट", "अंकपत्र"],
            cues={"statement of marks": 6, "marks obtained": 4, "grade": 1, "roll no": 2, "board of": 2, "university": 1, "cgpa": 3, "sgpa": 3},
            filename=["marksheet", "transcript", "result"]),
    DocType("degree_certificate", "Degree / certificate", "education",
            aliases=["degree", "degree certificate", "certificate", "diploma", "डिग्री", "प्रमाणपत्र"],
            cues={"this is to certify": 3, "degree of": 4, "conferred": 3, "has been awarded": 3, "certificate": 1.5}, filename=["degree", "certificate"]),
    DocType("resume", "Resume / CV", "education",
            aliases=["resume", "cv", "curriculum vitae", "biodata", "बायोडाटा"],
            cues={"curriculum vitae": 6, "resume": 3, "work experience": 3, "education": 1, "skills": 1.5, "objective": 1}, filename=["resume", "cv"]),
    DocType("offer_letter", "Offer / appointment letter", "education",
            aliases=["offer letter", "appointment letter", "joining letter", "relieving letter", "experience letter"],
            cues={"offer of employment": 5, "appointment letter": 5, "we are pleased to offer": 5, "relieving": 3, "date of joining": 3},
            filename=["offer", "appointment", "relieving"]),
    # ---------------- property / legal ----------------
    DocType("rental_agreement", "Rental agreement", "legal",
            aliases=["rental agreement", "rent agreement", "lease", "lease agreement", "tenancy agreement", "किराया अनुबंध", "किरायानामा"],
            cues={"rental agreement": 5, "rent agreement": 5, "lease": 2, "landlord": 3, "tenant": 3, "lessor": 3, "lessee": 3, "security deposit": 2},
            filename=["rent", "lease", "agreement"]),
    DocType("vehicle_rc", "Vehicle registration (RC)", "legal",
            aliases=["rc", "rc book", "registration certificate", "vehicle registration", "आरसी"],
            cues={"registration certificate": 4, "chassis no": 4, "engine no": 3, "owner name": 1, "regn": 2, "maker": 1}, filename=["rc"]),
]


def _from_json(d: dict) -> DocType:
    return DocType(id=d["id"], label=d.get("label", d["id"]), category=d.get("category", "document"), aliases=list(d.get("aliases", [])),
                   cues={k.lower(): float(v) for k, v in (d.get("cues") or {}).items()}, patterns=list(d.get("patterns", [])),
                   filename=list(d.get("filename", [])), visual=d.get("visual"), min_score=float(d.get("min_score", 4.0)))


@lru_cache
def registry() -> dict[str, DocType]:
    types = {t.id: t for t in BUILTIN}
    path = get_settings().doc_types_file
    if path and Path(path).exists():
        for d in json.loads(Path(path).read_text(encoding="utf-8")):
            types[d["id"]] = _from_json(d)  # user entries add new types or override built-ins
    for t in types.values():
        t.cues = {k.lower(): v for k, v in t.cues.items()}
        for p in t.patterns:
            p["_rx"] = re.compile(p["regex"])
            p["_rx_all"] = re.compile(rf"(?=({p['regex']}))")
    return types


def label(type_id: str | None) -> str | None:
    t = registry().get(type_id or "")
    return t.label if t else None


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _contains(hay: str, phrase: str) -> bool:
    # word-boundary match for short ASCII cues ("pan", "vid") so they don't hit inside other words
    if len(phrase) <= 4 and phrase.isascii():
        return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", hay) is not None
    return phrase in hay


def _name_tokens(filename: str) -> set[str]:
    stem = Path(filename).stem.lower()
    return set(re.split(r"[^a-z0-9]+", stem)) - {""}


@dataclass
class Classification:
    type_id: str | None
    confidence: float
    scores: dict[str, float]
    fields: dict[str, str]


def classify(text: str, filename: str = "", visual_scores: dict[str, float] | None = None) -> Classification:
    """Score every type from text cues, ID patterns, filename words and visual cues; return the best one."""
    hay = _norm(text)
    raw = " ".join(text.split())
    names = _name_tokens(filename)
    visual_scores = visual_scores or {}
    scores: dict[str, float] = {}
    fields: dict[str, dict[str, str]] = {}
    for t in registry().values():
        s = 0.0
        for cue, w in t.cues.items():
            if _contains(hay, cue):
                s += w
        for p in t.patterns:
            # overlapping scan: OCR often repeats/merges numbers ("2934 4733 1320 2934"), and the real one may overlap a false one
            hits = list(dict.fromkeys(m.group(1) for m in p["_rx_all"].finditer(raw)))
            check = CHECKS.get(p.get("check", ""))
            if check:
                hits = [h for h in hits if check(h)]
            if hits:
                s += p["weight"]
                if p.get("field"):
                    fields.setdefault(t.id, {})[p["field"]] = hits[0]
        if any(any(tok == w or (len(w) >= 4 and tok.startswith(w)) for tok in names) for w in t.filename):
            s += 3
        if t.visual and visual_scores.get(t.visual, 0) >= 0.5:
            s += 5 * visual_scores[t.visual]
        if s > 0:
            scores[t.id] = round(s, 2)
    if not scores:
        return Classification(None, 0.0, {}, {})
    best = max(scores, key=scores.get)
    t = registry()[best]
    if scores[best] < t.min_score:
        return Classification(None, 0.0, scores, {})
    ordered = sorted(scores.values(), reverse=True)
    margin = ordered[0] - (ordered[1] if len(ordered) > 1 else 0)
    conf = min(1.0, scores[best] / 10) * (0.6 + 0.4 * min(1.0, margin / 4))
    return Classification(best, round(conf, 2), scores, fields.get(best, {}))


# ---------------- query side ----------------

@lru_cache
def _alias_index() -> list[tuple[str, str]]:
    """(alias, type_id) sorted longest-first so 'pan card' wins over 'pan'."""
    pairs = [(a.lower(), t.id) for t in registry().values() for a in (t.aliases + [t.label])]
    return sorted(set(pairs), key=lambda x: -len(x[0]))


W = r"[\wऀ-෿]"
_TOK = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def _tok_eq(q: str, a: str) -> bool:
    """Token equality with typo tolerance for longer words: 'adhar'~'aadhar', 'pasport'~'passport', 'signture'~'signature'."""
    q = q[:-2] if q.endswith("'s") else q
    if q == a or (len(a) >= 4 and q in (a + "s", a + "es")):
        return True
    if len(a) < 5 or len(q) < 4 or not a.isalpha() or q[0] != a[0]:  # same first letter: "nature" must not become "signature"
        return False
    from difflib import SequenceMatcher
    return SequenceMatcher(None, q, a).ratio() >= (0.8 if len(a) >= 7 else 0.83)


@lru_cache
def _category_index() -> list[tuple[str, list[str]]]:
    from .concepts import CATEGORIES
    by_cat: dict[str, list[str]] = {}
    for t in registry().values():
        by_cat.setdefault(t.category, []).append(t.id)
    pairs = [(p.lower(), by_cat.get(cat, [])) for cat, phrases in CATEGORIES.items() for p in phrases]
    return sorted(pairs, key=lambda x: -len(x[0]))


def find_in_query(text: str) -> tuple[list[str], str]:
    """Return (doc type ids mentioned, text with those mentions removed).

    Matches exact aliases in any script, plurals, small typos in English aliases, and group words
    ("id proofs", "health records") which expand to every type in that group.
    """
    found: list[str] = []
    out = text
    for phrase, ids in _category_index():
        rx = re.compile(rf"(?<!{W}){re.escape(phrase)}(?!{W})", re.I)
        if ids and rx.search(out):
            found += [i for i in ids if i not in found]
            out = rx.sub(" ", out)
    for alias, tid in _alias_index():
        rx = re.compile(rf"(?<!{W}){re.escape(alias)}(?:'?s|es)?(?!{W})", re.I)
        if rx.search(out):
            if tid not in found:
                found.append(tid)
            out = rx.sub(" ", out)
    # typo-tolerant pass over English aliases (only for words not already explained)
    toks = _TOK.findall(out.lower())
    if toks:
        for alias, tid in _alias_index():
            if tid in found or not alias.isascii():
                continue
            at = alias.split()
            if len(at) == 1 and len(at[0]) < 5:
                continue  # 'pan', 'dl', 'rc': exact only
            for i in range(len(toks) - len(at) + 1):
                window = toks[i:i + len(at)]
                if all(_tok_eq(q, a) for q, a in zip(window, at)) and any(len(a) >= 5 for a in at):
                    found.append(tid)
                    for w in window:
                        out = re.sub(rf"(?<!{W}){re.escape(w)}(?!{W})", " ", out, count=1, flags=re.I)
                    break
    return found, out

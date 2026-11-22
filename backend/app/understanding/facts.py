"""Facts inside a file: the details people ask about ("what's my PAN number?", "rahul's date of birth").

Works on any text (OCR of a card, a PDF, a Word file): labelled dates, ID numbers, gender, phone, email,
address/PIN, amounts, policy/invoice numbers, generic "Label: value" lines, plus the names found by entities.py.
Each fact is {"key", "label", "value"}; keys are stable so questions can be mapped onto them (see FIELD_ASK).
"""
from __future__ import annotations

import re

_MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|january|february|march|april|june|july|august|september|october|november|december"
DATE = (rf"(?:\d{{1,2}}[/\-.]\d{{1,2}}[/\-.](?:19|20)\d{{2}}|(?:19|20)\d{{2}}[/\-.]\d{{1,2}}[/\-.]\d{{1,2}}|"
        rf"\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTHS})[a-z]*[,.]?\s+(?:19|20)\d{{2}}|(?:{_MONTHS})[a-z]*\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+(?:19|20)\d{{2}})")
DATE_RE = re.compile(DATE, re.I)

# (key, label, label regex) for dates: the first date after the label (same or next line) is its value
DATE_LABELS = [
    ("date_of_birth", "Date of birth", r"date\s*of\s*birth|d\.?\s*o\.?\s*b\.?|birth\s*date|born\s*on|year of birth|जन्म\s*तिथि|जन्म\s*की\s*तारीख|जन्मतारीख"),
    ("expiry_date", "Valid until", r"date\s*of\s*expiry|expiry\s*date|expires?\s*on|valid\s*(?:till|upto|up\s*to|until|thru)|validity|expiry"),
    ("issue_date", "Issued on", r"date\s*of\s*issue|issue\s*date|issued\s*on|date\s*of\s*issuance"),
    ("due_date", "Due date", r"due\s*date|payment\s*due|pay\s*by"),
    ("invoice_date", "Invoice date", r"invoice\s*date|bill\s*date|dated"),
    ("travel_date", "Travel date", r"date\s*of\s*journey|departure\s*date|travel\s*date|flight\s*date"),
]
VALUE_LABELS = [  # (key, label, label regex, value regex)
    ("policy_number", "Policy number", r"policy\s*(?:no|number|#)", r"[A-Z0-9][A-Z0-9/\-]{5,}"),
    ("invoice_number", "Invoice number", r"invoice\s*(?:no|number|#)|bill\s*(?:no|number)", r"[A-Z0-9][A-Z0-9/\-]{2,}"),
    ("account_number", "Account number", r"a/?c\s*(?:no|number)|account\s*(?:no|number)", r"[X\d][X\d\s-]{6,}\d"),
    ("ifsc", "IFSC", r"ifsc(?:\s*code)?", r"[A-Z]{4}0[A-Z0-9]{6}"),
    ("pnr", "PNR", r"pnr(?:\s*(?:no|number))?", r"[A-Z0-9]{6,10}"),
    ("enrolment_number", "Enrolment number", r"enrol(?:l)?ment\s*(?:no|number)", r"[\d/ ]{8,}"),
    ("vid", "VID", r"\bvid\b", r"\d{4}\s?\d{4}\s?\d{4}\s?\d{4}"),
    ("blood_group", "Blood group", r"blood\s*group", r"(?:A|B|AB|O)\s*[+-]|(?:A|B|AB|O)\s*(?:pos|neg|positive|negative)"),
]
GENDER_RE = re.compile(r"\b(male|female|transgender|पुरुष|महिला)\b", re.I)
MOBILE_RE = re.compile(r"(?<![\dA-Z])(?:\+?91[\s-]?)?(?:[6-9]\d{9}|[6-9]\d[X*]{6,7}\d{1,2})(?![\dA-Z])")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")
PIN_RE = re.compile(r"(?:pin(?:\s*code)?|pincode|-)\s*[:\-]?\s*([1-9]\d{2}\s?\d{3})(?!\d)", re.I)
AMOUNT_RE = re.compile(r"(?:₹|rs\.?|inr|\$|usd|€|eur|£)\s?([\d,]+(?:\.\d{1,2})?)", re.I)
AMOUNT_LABEL_RE = re.compile(r"(grand\s*total|total\s*amount|amount\s*(?:due|payable|paid)|net\s*pay(?:able)?|total|premium|balance)\s*[:\-]?\s*"
                             r"(?:₹|rs\.?|inr|\$|usd|€|eur|£)?\s?([\d,]+(?:\.\d{1,2})?)", re.I)
ADDRESS_RE = re.compile(r"(?<!abha )(?<!e-mail )(?<!email )(?:address|addr|पता)\s*[:/\-]?\s*(.+)", re.I)
LABELISH = re.compile(r"\b(?:gender|date of birth|dob|mobile|phone|email|name)\b\s*/?", re.I)
KV_RE = re.compile(r"^\s*([A-Za-z][A-Za-z .'/]{2,30}?)\s*[:：]\s*(\S.{0,60})$")
KV_SKIP = re.compile(r"https?|www\.|tel|fax|page|note", re.I)

# id-number fields captured by doc_types patterns -> friendly label
FIELD_LABELS = {"pan_number": "PAN number", "aadhaar_number": "Aadhaar number", "abha_number": "ABHA number", "abha_address": "ABHA address",
                "epic_number": "Voter ID number", "passport_number": "Passport number", "dl_number": "Licence number", "mrz": "Passport code"}

# question words -> fact keys they ask about (used by the query parser)
FIELD_ASK: list[tuple[str, list[str]]] = [
    (r"date of birth|dob|birth ?day|birth date|born|age|जन्म", ["date_of_birth"]),
    (r"father'?s?(?: name)?|dad'?s? name|pita|पिता", ["father_name"]),
    (r"(?:valid|validity|expir\w*|valid till|valid until|renew)", ["expiry_date"]),
    (r"issue date|issued|date of issue", ["issue_date"]),
    (r"due date|due|pay by", ["due_date"]),
    (r"gender|sex|लिंग", ["gender"]),
    (r"mobile|phone|contact number|cell|मोबाइल", ["mobile"]),
    (r"e-?mail", ["email"]),
    (r"address|where does|पता", ["address", "abha_address", "pin_code"]),
    (r"pin ?code|pincode", ["pin_code"]),
    (r"amount|total|how much|cost|price|premium|balance|पैसे|कितना", ["amount_total", "amount"]),
    (r"policy (?:no|number)", ["policy_number"]),
    (r"invoice (?:no|number)|bill (?:no|number)", ["invoice_number"]),
    (r"account (?:no|number)|a/c", ["account_number"]),
    (r"ifsc", ["ifsc"]),
    (r"pnr", ["pnr"]),
    (r"blood group", ["blood_group"]),
    (r"vid\b", ["vid"]),
    (r"whose|holder|owner|belongs?|name on|who is|किसका|नाम", ["holder"]),
    (r"number|no\.?|id|नंबर|संख्या|नम्बर", ["id_number"]),  # generic "number": the document's own ID number
]
FIELD_ASK_RE = [(re.compile(rf"(?<![\w]){p}(?![\w])", re.I), keys) for p, keys in FIELD_ASK]


def _first_after(text: str, label_rx: str, value_rx: str, span: int = 60) -> str | None:
    for m in re.finditer(label_rx, text, re.I):
        tail = text[m.end():m.end() + span]
        v = re.search(value_rx, tail, re.I)
        if v:
            return v.group(0).strip(" ,.;:")
    return None


def extract_facts(text: str, *, fields: dict[str, str] | None = None, names: dict | None = None) -> list[dict]:
    facts: list[dict] = []
    seen: set[str] = set()

    def add(key: str, label: str, value: str | None):
        if not value:
            return
        value = " ".join(str(value).split())[:120]
        if key in seen or not value:
            return
        seen.add(key)
        facts.append({"key": key, "label": label, "value": value})

    flat = " ".join(text.split())
    names = names or {}
    if names.get("holder"):
        add("holder", "Name", names["holder"][0])
    if names.get("relatives"):
        rel_line = re.search(r"(father'?s?\s*name|s/o|son of|d/o|daughter of)", text, re.I)
        add("father_name" if rel_line else "relative", "Father's name" if rel_line else "Related person", names["relatives"][0])
    for k, v in (fields or {}).items():
        add(k, FIELD_LABELS.get(k, k.replace("_", " ").capitalize()), v)
    for key, label, rx in DATE_LABELS:
        add(key, label, _first_after(text, rx, DATE, 50))
    for key, label, lrx, vrx in VALUE_LABELS:
        add(key, label, _first_after(flat, lrx, vrx, 40))
    g = GENDER_RE.search(text)
    if g:
        add("gender", "Gender", {"पुरुष": "Male", "महिला": "Female"}.get(g.group(1), g.group(1).capitalize()))
    m = MOBILE_RE.search(flat)
    if m:
        add("mobile", "Mobile", m.group(0))
    e = EMAIL_RE.search(flat)
    if e and not e.group(0).lower().endswith(("@abdm", "@sbx")):
        add("email", "Email", e.group(0))
    a = ADDRESS_RE.search(text)
    if a:
        lines = []
        for ln in text[a.start(1):].splitlines()[:4]:
            if LABELISH.search(ln) or "@" in ln:
                break
            if ln.strip(" ,"):
                lines.append(ln.strip(" ,"))
        if lines and len(" ".join(lines)) > 8:
            add("address", "Address", ", ".join(lines)[:120])
    p = PIN_RE.search(flat)
    if p and ("address" in seen or re.search(r"pin\s*code|pincode|\bpin\b", flat, re.I)):
        add("pin_code", "PIN code", p.group(1).replace(" ", ""))  # only when it belongs to an address, not an office on the back
    am = AMOUNT_LABEL_RE.search(flat)
    if am:
        add("amount_total", am.group(1).strip().capitalize(), am.group(2))
    else:
        amounts = [x.group(1) for x in AMOUNT_RE.finditer(flat)]
        if amounts:
            add("amount", "Amount", max(amounts, key=lambda s: float(s.replace(",", "") or 0)))
    # generic "Label: value" lines from forms, letters and reports
    n = 0
    for ln in text.splitlines():
        kv = KV_RE.match(ln)
        if kv and not KV_SKIP.search(kv.group(1)) and n < 12:
            key = "kv_" + re.sub(r"\W+", "_", kv.group(1).strip().lower())[:30]
            add(key, kv.group(1).strip().capitalize(), kv.group(2))
            n += 1
    if not any(f["key"] == "date_of_birth" for f in facts):
        d = DATE_RE.findall(text)
        if d and len(set(d)) == 1 and names.get("holder"):
            add("date", "Date", d[0])  # an ID card with exactly one date: almost always the birth date, but don't claim it
    return facts


def facts_sentence(facts: list[dict]) -> str:
    return " ".join(f"{f['label']}: {f['value']}." for f in facts if not f["key"].startswith("kv_"))[:900]


def asked_fields(question: str) -> list[str]:
    """Fact keys a question asks for, most specific first ('father's name' beats 'name')."""
    out: list[str] = []
    for rx, keys in FIELD_ASK_RE:
        if rx.search(question):
            out += [k for k in keys if k not in out]
    return out

"""Query understanding: language detect -> rule-based filters (dates/kinds/places) -> optional LLM rewrite.

Relative dates are ALWAYS resolved here (user timezone + today), never by the LLM alone.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from ..adapters.embeddings import tokenize
from ..adapters.llm import parse_json_loose

W = r"[\wऀ-෿]"


def _ph(p: str) -> re.Pattern:
    return re.compile(rf"(?<!{W})(?:{p})(?!{W})", re.I)


MONTHS: dict[str, int] = {}
for lang_names in (
    "january february march april may june july august september october november december",
    "jan feb mar apr may jun jul aug sep sept oct nov dec",
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre",
    "जनवरी फरवरी फ़रवरी मार्च अप्रैल मई जून जुलाई अगस्त सितंबर सितम्बर अक्टूबर नवंबर नवम्बर दिसंबर दिसम्बर",
    "जानेवारी फेब्रुवारी मार्च एप्रिल मे जून जुलै ऑगस्ट सप्टेंबर ऑक्टोबर नोव्हेंबर डिसेंबर",
    "ஜனவரி பிப்ரவரி மார்ச் ஏப்ரல் மே ஜூன் ஜூலை ஆகஸ்ட் செப்டம்பர் அக்டோபர் நவம்பர் டிசம்பர்",
):
    names = lang_names.split()
    if len(names) == 12:
        for i, n in enumerate(names, 1):
            MONTHS[n] = i
MONTHS.update({"jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
               "सितंबर": 9, "सितम्बर": 9, "नवंबर": 11, "नवम्बर": 11, "दिसंबर": 12, "दिसम्बर": 12, "फ़रवरी": 2, "फरवरी": 2})

KIND_WORDS = {
    "photo": "photo photos picture pictures pic pics image images foto fotos imagen imágenes फोटो फोटोज तस्वीर तस्वीरें चित्र छायाचित्र புகைப்படம் புகைப்படங்கள்",
    "video": "video videos clip clips movie movies vídeo vídeos वीडियो व्हिडिओ व्हिडीओ காணொளி வீடியோ",
    "document": "document documents doc docs pdf pdfs paperwork documento documentos दस्तावेज़ दस्तावेज कागज़ कागजात ஆவணம் ஆவணங்கள்",
}
KIND_LOOKUP = {w: k for k, ws in KIND_WORDS.items() for w in ws.split()}

REL = {
    "last_year": r"last year|previous year|पिछले साल|पिछले वर्ष|गेल्या वर्षी|गेल्या वर्ष|(?:el )?año pasado|கடந்த ஆண்டு|கடந்த வருடம்",
    "this_year": r"this year|इस साल|इस वर्ष|या वर्षी|este año|இந்த ஆண்டு",
    "last_month": r"last month|पिछले महीने|गेल्या महिन्यात|(?:el )?mes pasado|கடந்த மாதம்",
    "this_month": r"this month|इस महीने|या महिन्यात|este mes|இந்த மாதம்",
    "last_week": r"last week|पिछले हफ्ते|पिछले सप्ताह|गेल्या आठवड्यात|(?:la )?semana pasada|கடந்த வாரம்",
    "yesterday": r"yesterday|ayer|நேற்று",
    "today": r"today|आज|hoy|இன்று",
}
REL_RE = {k: _ph(v) for k, v in REL.items()}
AGO_RE = _ph(r"(\d+)\s*(day|week|month|year)s?\s+ago")
YEAR_RE = _ph(r"(?:19|20)\d{2}")
LAST_PREFIX = _ph(r"(?:last|previous|पिछले|गेल्या|கடந்த)\s+$")

QUESTION_START = {"what", "when", "where", "who", "whom", "whose", "how", "why", "which", "does", "do", "is", "are", "can", "did", "was", "will",
                  "क्या", "कब", "कहाँ", "कहां", "कौन", "कैसे", "कितना", "कितनी", "कोणते", "केव्हा", "कुठे", "काय", "कसे",
                  "qué", "que", "cuándo", "cuando", "dónde", "donde", "quién", "quien", "cómo", "como", "cuánto", "cuanto", "cuál",
                  "என்ன", "எப்போது", "எங்கே", "யார்", "எப்படி", "எவ்வளவு"}
FOLLOWUP_CUES = {"only", "just", "also", "same", "instead", "those", "these", "filter", "then", "sólo", "solo", "सिर्फ", "केवल", "फिर", "अब"}
LEAD_FILLER = _ph(r"^(?:please\s+)?(?:can you\s+|could you\s+)?(?:show me|show|find me|find|search for|search|look for|give me|i want to see|i want|i need|get me|display)\s+(?:all\s+)?(?:my\s+)?")
CUE_STRIP = {"only", "just", "also", "instead", "now", "then", "same", "those", "these", "filter", "सिर्फ", "केवल", "अब", "sólo", "solo"}
TRIM_WORDS = {"की", "का", "के", "में", "से", "और", "को", "पर", "ची", "चा", "चे", "मध्ये", "ला", "आणि", "இல்", "மற்றும்", "of", "from", "in", "the", "a", "an", "with", "for", "during", "on", "at", "to", "and", "my", "me", "about", "de", "del", "en", "con", "las", "los", "el", "la"}
STOP = set("की का के में से और को पर है हैं ची चा चे च मध्ये ला आणि हे ही आहे".split()) | set("a an the of in on at to for from with and or is are was were be been it its this that these those my me i you your as by about into than then so if not no do does did what when where who whom how which can will would should have has had".split()) | \
    set("de la el los las un una y o en con por para del al que se es".split())


@dataclass
class Filters:
    kinds: list[str] = field(default_factory=list)
    date_from: str | None = None
    date_to: str | None = None
    place: str | None = None
    tags: list[str] = field(default_factory=list)
    language: str | None = None
    collection_id: str | None = None

    def as_dict(self) -> dict:
        return {"kinds": self.kinds, "date_from": self.date_from, "date_to": self.date_to, "place": self.place,
                "tags": self.tags, "language": self.language, "collection_id": self.collection_id}

    @classmethod
    def from_dict(cls, d: dict | None) -> "Filters":
        d = d or {}
        return cls(kinds=list(d.get("kinds") or []), date_from=d.get("date_from"), date_to=d.get("date_to"), place=d.get("place"),
                   tags=list(d.get("tags") or []), language=d.get("language"), collection_id=d.get("collection_id"))


@dataclass
class ParsedQuery:
    raw: str
    language: str | None = None
    intent: str = "mixed"
    semantic_query: str = ""
    semantic_query_en: str | None = None
    filters: Filters = field(default_factory=Filters)
    followup: bool = False

    def as_dict(self) -> dict:
        return {"raw": self.raw, "language": self.language, "intent": self.intent, "semantic_query": self.semantic_query,
                "semantic_query_en": self.semantic_query_en, "filters": self.filters.as_dict(), "followup": self.followup}

    @classmethod
    def from_dict(cls, d: dict) -> "ParsedQuery":
        return cls(raw=d.get("raw", ""), language=d.get("language"), intent=d.get("intent", "mixed"), semantic_query=d.get("semantic_query", ""),
                   semantic_query_en=d.get("semantic_query_en"), filters=Filters.from_dict(d.get("filters")), followup=bool(d.get("followup")))


def _month_range(y: int, m: int) -> tuple[date, date]:
    return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])


def _cut(text: str, m: re.Match) -> str:
    return (text[:m.start()] + " " + text[m.end():])


def _extract_dates(text: str, today: date) -> tuple[str, date | None, date | None]:
    lo = hi = None
    # relative phrases
    for key, rx in REL_RE.items():
        m = rx.search(text)
        if not m:
            continue
        text = _cut(text, m)
        if key == "last_year":
            lo, hi = date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)
        elif key == "this_year":
            lo, hi = date(today.year, 1, 1), today
        elif key == "last_month":
            y, mo = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
            lo, hi = _month_range(y, mo)
        elif key == "this_month":
            lo, hi = date(today.year, today.month, 1), today
        elif key == "last_week":
            start = today - timedelta(days=today.weekday() + 7)
            lo, hi = start, start + timedelta(days=6)
        elif key == "yesterday":
            lo = hi = today - timedelta(days=1)
        elif key == "today":
            lo = hi = today
        return text, lo, hi
    m = AGO_RE.search(text)
    if m:
        n, unit = int(m[1]), m[2].lower()
        text = _cut(text, m)
        if unit == "year":
            return text, date(today.year - n, 1, 1), date(today.year - n, 12, 31)
        if unit == "month":
            idx = today.year * 12 + today.month - 1 - n
            lo, hi = _month_range(idx // 12, idx % 12 + 1)
            return text, lo, hi
        days = n * (7 if unit == "week" else 1)
        d = today - timedelta(days=days)
        return text, d, d

    year = None
    ym = YEAR_RE.search(text)
    if ym:
        year = int(ym[0])
        text = _cut(text, ym)
    month = None
    for tok_m in re.finditer(rf"(?<!{W})({W}+)(?!{W})", text):
        w = tok_m[1].lower()
        if w in MONTHS and not (w in {"may", "mar", "sep"} and False):
            month = MONTHS[w]
            start, end = tok_m.start(), tok_m.end()
            pre = LAST_PREFIX.search(text[:start] + " ")
            if pre:
                start = pre.start()
            post = re.match(r"\s+pasado(?!\w)", text[end:])
            if post:
                end += post.end()
            text = text[:start] + " " + text[end:]
            break
    if month and year:
        lo, hi = _month_range(year, month)
    elif month:
        y = today.year if month <= today.month else today.year - 1  # most recent past occurrence
        lo, hi = _month_range(y, month)
    elif year:
        lo, hi = date(year, 1, 1), date(year, 12, 31)
    return text, lo, hi


def rule_parse(raw: str, *, today: date, places: list[str] | None = None, lang: str | None = None) -> ParsedQuery:
    text = " " + raw.strip() + " "
    q = ParsedQuery(raw=raw, language=lang)
    text, lo, hi = _extract_dates(text, today)
    q.filters.date_from = lo.isoformat() if lo else None
    q.filters.date_to = hi.isoformat() if hi else None

    kinds: list[str] = []

    def kind_sub(m: re.Match) -> str:
        k = KIND_LOOKUP.get(m[0].lower())
        if k and k not in kinds:
            kinds.append(k)
        return " "
    text = re.sub(rf"(?<!{W})({'|'.join(sorted(map(re.escape, KIND_LOOKUP), key=len, reverse=True))})(?!{W})", kind_sub, text, flags=re.I)
    q.filters.kinds = kinds

    # place: match any comma-part of a known place from the user's own library
    low = text.lower()
    for part in sorted({p.strip() for pl in (places or []) for p in pl.split(",") if len(p.strip()) >= 3}, key=len, reverse=True):
        m = _ph(re.escape(part.lower())).search(low)
        if m:
            q.filters.place = part
            text = text[:m.start()] + " " + text[m.end():]
            low = text.lower()
            break

    text = LEAD_FILLER.sub("", text.strip())
    words = text.split()
    while words and words[0].lower().strip("?.,!") in TRIM_WORDS:
        words.pop(0)
    while words and words[-1].lower().strip("?.,!") in TRIM_WORDS:
        words.pop()
    if words and words[0].lower() == "show":
        words.pop(0)
    words = [w for w in words if w.lower() not in {"instead"}]
    while words and words[0].lower() in CUE_STRIP:
        words.pop(0)
    while words and words[0].lower().strip("?.,!") in TRIM_WORDS:
        words.pop(0)
    q.semantic_query = " ".join(words).strip(" ?.,!")

    toks = tokenize(raw)
    first = toks[0] if toks else ""
    q.followup = bool(toks) and len(toks) <= 7 and (first in FOLLOWUP_CUES or "instead" in toks)
    is_question = raw.strip().endswith("?") or first in QUESTION_START or "?" in raw
    if is_question and kinds in ([], ["document"]):
        q.intent = "answer_question"
    elif kinds == ["document"]:
        q.intent = "find_document"
    elif kinds and "document" not in kinds:
        q.intent = "find_media"
    else:
        q.intent = "mixed"
    return q


def merge_followup(new: ParsedQuery, prev: ParsedQuery) -> ParsedQuery:
    """Carry context from the previous turn: 'only 2023', 'show videos instead', 'and in Goa'."""
    inherits_text = not new.semantic_query or (new.followup and len(new.semantic_query.split()) <= 3 and not new.semantic_query.lower() in {"only", "just"})
    f, pf = new.filters, prev.filters
    merged = Filters(
        kinds=f.kinds or pf.kinds, date_from=f.date_from or pf.date_from, date_to=f.date_to or pf.date_to,
        place=f.place or pf.place, tags=f.tags or pf.tags, language=f.language or pf.language, collection_id=f.collection_id or pf.collection_id)
    if f.date_from is None and f.date_to is None:
        merged.date_from, merged.date_to = pf.date_from, pf.date_to
    out = ParsedQuery(raw=new.raw, language=new.language or prev.language, filters=merged, followup=True)
    if inherits_text:
        cue = {"only", "just", "also", "and", "now", "show", "same", "instead", "those", "these", "filter", "then"}
        extra = " ".join(w for w in new.semantic_query.split() if w.lower() not in cue) if new.semantic_query else ""
        out.semantic_query = (prev.semantic_query + (" " + extra if extra else "")).strip()
        out.intent = prev.intent if not f.kinds else new.intent
    else:
        out.semantic_query, out.intent = new.semantic_query, new.intent
    out.semantic_query_en = prev.semantic_query_en if out.semantic_query == prev.semantic_query else None
    return out


def llm_enrich(q: ParsedQuery, llm) -> ParsedQuery:
    """Optional: let an LLM rewrite the query and add an English translation. Dates/filters stay rule-based."""
    try:
        sys = ("You rewrite search queries for a personal photo/video/document search. Reply ONLY with JSON: "
               '{"semantic_query": "...", "semantic_query_en": "English translation"} '
               "Keep it short, no dates, no file types.")
        d = parse_json_loose(llm.complete(sys, q.semantic_query or q.raw, json_mode=True))
        if d:
            q.semantic_query = str(d.get("semantic_query") or q.semantic_query)[:300]
            q.semantic_query_en = str(d.get("semantic_query_en") or "")[:300] or None
    except Exception:
        pass  # fall back to the rule-based parse
    return q


def parse_query(raw: str, *, tz: str, places: list[str], prev: dict | None = None, llm=None, lang: str | None = None,
                today: date | None = None) -> ParsedQuery:
    if today is None:
        try:
            today = datetime.now(ZoneInfo(tz)).date()
        except Exception:
            today = date.today()
    q = rule_parse(raw, today=today, places=places, lang=lang)
    if prev:
        p = ParsedQuery.from_dict(prev)
        if q.followup or not q.semantic_query:
            q = merge_followup(q, p)
    if llm is not None and getattr(llm, "supports_json", False) and q.semantic_query:
        q = llm_enrich(q, llm)
    return q

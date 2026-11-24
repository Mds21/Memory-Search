"""Vocabulary that lets plain questions reach the right files without a language model.

* CATEGORIES: group words ("ID proof", "KYC", "health records", "bills") -> every document type in that group.
* SYNONYMS: everyday words -> words the index actually contains ("ocean" finds photos tagged "beach").
* fuzzy(): typo tolerance ("adhar", "pasport", "signture") against a vocabulary.
All plain data: extend freely.
"""
from __future__ import annotations

from difflib import get_close_matches

CATEGORIES: dict[str, list[str]] = {
    # category id (doc_types.DocType.category) or explicit type lists -> phrases
    "id": ["id proof", "id proofs", "identity proof", "identity proofs", "identity documents", "identity document", "id documents",
           "id document", "id cards", "identity cards", "government id", "government ids", "govt id", "photo id", "kyc", "kyc documents",
           "address proof", "address proofs", "pehchan patra", "पहचान पत्र", "आईडी प्रूफ", "पहचान", "documentos de identidad"],
    "health": ["health documents", "health records", "medical documents", "medical records", "medical papers", "hospital documents",
               "स्वास्थ्य दस्तावेज़", "मेडिकल रिपोर्ट"],
    "finance": ["financial documents", "finance documents", "money documents", "bank documents", "tax documents", "bills and receipts",
                "payment documents", "वित्तीय दस्तावेज़"],
    "travel": ["travel documents", "travel papers", "tickets", "trip documents", "यात्रा दस्तावेज़"],
    "education": ["education documents", "educational documents", "academic documents", "certificates", "school documents",
                  "college documents", "job documents", "work documents", "शैक्षिक दस्तावेज़"],
    "legal": ["legal documents", "property documents", "property papers", "agreements", "contracts", "कानूनी दस्तावेज़"],
    "personal": ["personal documents", "personal papers"],
}

SYNONYMS: dict[str, list[str]] = {
    "beach": ["sea", "ocean", "coast", "shore", "seaside", "sand", "seashore", "bay", "samundar", "समुद्र", "बीच", "playa"],
    "sea": ["ocean", "beach", "water", "coast"],
    "mountain": ["mountains", "hills", "hill", "peak", "trek", "trekking", "pahad", "पहाड़", "montaña"],
    "snow": ["winter", "ice", "snowfall", "बर्फ"],
    "greenery": ["trees", "tree", "forest", "nature", "park", "garden", "plants", "jungle", "green", "पेड़"],
    "sunset": ["sunrise", "dusk", "dawn", "evening", "golden hour", "सूर्यास्त"],
    "night": ["dark", "night time", "रात"],
    "sky": ["clouds", "cloud", "आसमान"],
    "signature": ["sign", "autograph", "signed", "हस्ताक्षर"],
    "document": ["paper", "papers", "scan", "scanned", "card", "दस्तावेज़", "कागज़"],
    "screenshot": ["screen shot", "screengrab", "screen capture"],
    "photo": ["picture", "pic", "image", "snap", "photograph", "click"],
    "invoice": ["bill", "receipt", "payment"],
    "certificate": ["certificates", "proof"],
}

_REVERSE: dict[str, set[str]] = {}
for head, words in SYNONYMS.items():
    group = {head, *words}
    for w in group:
        _REVERSE.setdefault(w, set()).update(group - {w})


def expand(terms: list[str]) -> list[str]:
    """Query terms plus their synonyms (synonyms only; the caller keeps the originals separately)."""
    out: list[str] = []
    for t in terms:
        for s in sorted(_REVERSE.get(t, ())):
            if " " not in s and s not in terms and s not in out:
                out.append(s)
    return out


def fuzzy(word: str, vocab: list[str] | set[str], *, cutoff: float | None = None) -> list[str]:
    """Close spellings of `word` in `vocab` (short words must match exactly)."""
    if len(word) < 4:
        return []
    c = cutoff or (0.88 if len(word) <= 5 else 0.8)
    return get_close_matches(word, list(vocab), n=2, cutoff=c)

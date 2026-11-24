"""What a picture shows, from the image model's fingerprint (CLIP zero-shot labelling).

Every photo and video frame already gets a CLIP image embedding for search. Comparing it with short descriptions of
everyday subjects ("a handwritten signature", "a robot", "a beach") names what is in the picture, so the file gets
real tags, a real caption and a sensible title instead of "a bright photo with white and gray tones", and the chat
assistant can tell the person it found their signature. Runs locally; the label texts are embedded once.
"""
from __future__ import annotations

import threading

import numpy as np

# key -> (descriptions the image is compared with, tags, title, caption phrase)
LABELS: dict[str, tuple[list[str], list[str], str, str]] = {
    "signature": (["a handwritten signature in ink on white paper", "a person's signature autograph"],
                  ["signature", "handwritten signature", "sign", "autograph"], "Signature", "a handwritten signature"),
    "id_card": (["an identity card with a person's photo and printed details", "a government issued ID card"],
                ["id card", "identity card", "card", "document"], "ID card", "an identity card"),
    "document": (["a printed document page with text", "a scanned paper document", "a printed form or letter"],
                 ["document", "paper", "text"], "Document", "a document with printed text"),
    "receipt": (["a shop receipt or bill", "an invoice"], ["receipt", "bill", "invoice"], "Receipt", "a receipt or bill"),
    "screenshot": (["a screenshot of a phone screen", "a screenshot of a computer screen"], ["screenshot"], "Screenshot", "a screenshot"),
    "qr_code": (["a QR code"], ["qr code"], "QR code", "a QR code"),
    "logo": (["a company logo", "a brand logo design"], ["logo", "brand"], "Logo", "a logo"),
    "chart": (["a chart or graph", "a table of numbers"], ["chart", "graph"], "Chart", "a chart or graph"),
    "map": (["a map"], ["map"], "Map", "a map"),
    "handwriting": (["handwritten notes on paper"], ["handwriting", "notes"], "Handwritten notes", "handwritten notes"),
    "beach": (["a beach with sea and sand", "a tropical beach with palm trees"], ["beach", "sea", "ocean", "sand", "coast"], "Beach", "a beach"),
    "mountain": (["mountains", "a mountain landscape"], ["mountain", "mountains", "hills"], "Mountains", "mountains"),
    "sunset": (["a sunset sky", "a sunrise"], ["sunset", "sunrise", "sky"], "Sunset", "a sunset"),
    "snow": (["a snowy landscape"], ["snow", "winter"], "Snow", "snow"),
    "forest": (["a forest with trees", "green trees and nature"], ["forest", "trees", "nature", "greenery"], "Greenery", "trees and greenery"),
    "waterbody": (["a river or lake", "a waterfall"], ["river", "lake", "water"], "River or lake", "a river or lake"),
    "city": (["a city street with buildings", "a city skyline"], ["city", "street", "buildings"], "City", "a city scene"),
    "building": (["a building or monument", "a palace or fort"], ["building", "monument", "architecture"], "Building", "a building"),
    "temple": (["a temple", "a church or mosque"], ["temple", "religious place"], "Temple", "a place of worship"),
    "garden": (["a garden with flowers", "a close-up of a flower"], ["flower", "flowers", "garden"], "Flowers", "flowers"),
    "night": (["a night-time scene with lights"], ["night"], "Night", "a night scene"),
    "person": (["a portrait photo of a person", "a photo of a man", "a photo of a woman"], ["person", "people", "portrait"], "Portrait", "a person"),
    "selfie": (["a selfie"], ["selfie", "person"], "Selfie", "a selfie"),
    "group": (["a group of people", "a family photo"], ["group", "people", "family"], "Group photo", "a group of people"),
    "child": (["a baby", "a young child"], ["baby", "child", "kid"], "Child", "a child"),
    "wedding": (["a wedding ceremony", "a bride and groom"], ["wedding", "marriage"], "Wedding", "a wedding"),
    "party": (["a birthday party", "a celebration with decorations"], ["party", "celebration", "birthday"], "Celebration", "a celebration"),
    "food": (["a plate of food", "a meal on a table"], ["food", "meal"], "Food", "food"),
    "cake": (["a cake"], ["cake", "dessert"], "Cake", "a cake"),
    "dog": (["a dog"], ["dog", "pet", "animal"], "Dog", "a dog"),
    "cat": (["a cat"], ["cat", "pet", "animal"], "Cat", "a cat"),
    "bird": (["a bird"], ["bird", "animal"], "Bird", "a bird"),
    "animal": (["a wild animal", "a cow or horse"], ["animal"], "Animal", "an animal"),
    "car": (["a car"], ["car", "vehicle"], "Car", "a car"),
    "bike": (["a motorcycle", "a bicycle"], ["bike", "motorcycle", "bicycle", "vehicle"], "Bike", "a bike"),
    "train": (["a train"], ["train", "railway"], "Train", "a train"),
    "airplane": (["an airplane", "the view from an airplane window"], ["airplane", "flight"], "Flight", "an airplane"),
    "robot": (["a robot", "a humanoid robot or android head", "a metallic artificial human head"], ["robot", "android", "ai", "technology"],
              "Robot", "a robot or android"),
    "statue": (["a statue or sculpture"], ["statue", "sculpture"], "Statue", "a statue"),
    "art": (["a painting", "a digital artwork or illustration"], ["art", "painting", "artwork"], "Artwork", "an artwork"),
    "computer": (["a laptop or computer"], ["computer", "laptop"], "Computer", "a computer"),
    "phone": (["a mobile phone"], ["phone", "mobile"], "Phone", "a phone"),
    "book": (["a book"], ["book"], "Book", "a book"),
    "sports": (["people playing sports", "a cricket or football match"], ["sports", "game"], "Sports", "a sports scene"),
}
SCALE = 100.0        # CLIP's logit scale
MIN_TOP = 0.4        # keep the best label only if the model is at least this sure (softmax over all descriptions)
MIN_EXTRA = 0.25     # further labels

_lock = threading.Lock()
_cache: dict[str, tuple[list[str], np.ndarray]] = {}


def _label_matrix(embedder) -> tuple[list[str], np.ndarray]:
    if embedder.name not in _cache:
        with _lock:
            if embedder.name not in _cache:
                keys, texts = [], []
                for k, (prompts, *_rest) in LABELS.items():
                    for p in prompts:
                        keys.append(k)
                        texts.append(p)
                m = np.asarray(embedder.embed_text(texts), dtype=np.float32)
                m /= np.linalg.norm(m, axis=1, keepdims=True) + 1e-9
                _cache[embedder.name] = (keys, m)
    return _cache[embedder.name]


def scores(image_vec, embedder) -> dict[str, float]:
    """label -> probability (0..1, summing to about 1 over all labels) for one image embedding."""
    keys, m = _label_matrix(embedder)
    v = np.asarray(image_vec, dtype=np.float32)
    v = v / (np.linalg.norm(v) + 1e-9)
    logits = (m @ v) * SCALE
    p = np.exp(logits - logits.max())
    p /= p.sum()
    out: dict[str, float] = {}
    for k, x in zip(keys, p):
        out[k] = out.get(k, 0.0) + float(x)
    return out


def labels(image_vec, embedder) -> list[tuple[str, float]]:
    """The labels worth keeping, best first (at most three)."""
    ranked = sorted(scores(image_vec, embedder).items(), key=lambda kv: -kv[1])
    if not ranked or ranked[0][1] < MIN_TOP:
        return []
    return [ranked[0]] + [(k, s) for k, s in ranked[1:3] if s >= MIN_EXTRA]


def as_cues(found: list[tuple[str, float]]) -> dict[str, float]:
    """Labels in the 0..1 'cue' scale the rest of understanding uses (>= 0.5 means "yes, this")."""
    return {k: round(min(1.0, 0.5 + s), 2) for k, s in found}

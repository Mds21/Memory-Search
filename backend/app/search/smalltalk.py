"""Small talk: greetings, thanks, "who are you", "what can you do". These skip file search entirely (no stray
matches for "hello"), go to the model with no file sources, and have fixed persona replies for when no model runs.
Only short messages that are nothing but small talk count: "hi, show my beach photos" is still a search."""
from __future__ import annotations

import re

_FILLER = r"(?:\s+(?:there|again|smriti|memory search|bot|buddy|friend|so much|a lot|very much|ji|sir|ma'?am))*"
PATTERNS: list[tuple[str, re.Pattern]] = [(k, re.compile(rf"^(?:{p}){_FILLER}$", re.I)) for k, p in [
    ("greet", r"hi+|hello+|hey+|hiya|yo|hola|namaste|namaskar|namaskaram|vanakkam|good\s+(?:morning|afternoon|evening|day)"
              r"|नमस्ते|नमस्कार|हैलो|வணக்கம்|ஹலோ|buenos\s+d[ií]as|buenas(?:\s+(?:tardes|noches))?"),
    ("how", r"how\s+(?:are|r)\s+(?:you|u)(?:\s+doing)?|how'?s\s+it\s+going|what'?s\s+up|sup|kaise\s+ho|कैसे\s+हो|कसे\s+आहात|எப்படி\s+இருக்கீங்க|c[oó]mo\s+est[aá]s"),
    ("thanks", r"thanks?(?:\s+you)?|thank\s+u|thx|ty|cheers|great|awesome|perfect|nice|cool|ok(?:ay)?\s+thanks?|dhanyavaa?d|shukriya"
               r"|धन्यवाद|शुक्रिया|धन्यवाद\s+जी|நன்றி|gracias"),
    ("bye", r"bye+|goodbye|good\s*night|see\s+(?:you|ya)(?:\s+later)?|tata|alvida|अलविदा|போய்\s+வருகிறேன்|adi[oó]s"),
    ("identity", r"who\s+(?:are|r)\s+(?:you|u)|what\s+(?:are|r)\s+(?:you|u)|what'?s\s+your\s+name|your\s+name|are\s+you\s+(?:a\s+)?(?:bot|ai|human|real)"
                 r"|tum\s+kaun\s+ho|aap\s+kaun\s+hain|तुम\s+कौन\s+हो|आप\s+कौन\s+हैं|நீ\s+யார்|qui[eé]n\s+eres"),
    ("help", r"help|what\s+can\s+(?:you|u)\s+do|what\s+do\s+(?:you|u)\s+do|how\s+(?:do|does)\s+(?:this|it|you)\s+work|how\s+(?:do\s+i|to)\s+use\s+(?:this|it|you)"
             r"|what\s+is\s+(?:this|smriti|memory\s+search)|what\s+can\s+i\s+(?:ask|search)|tum\s+kya\s+kar\s+sakte\s+ho|आप\s+क्या\s+कर\s+सकते\s+हैं|qu[eé]\s+puedes\s+hacer"),
]]

_PUNCT = re.compile(r"[\s!?.,;:~*\"()\[\]{}…।]+")  # apostrophes stay: "what's", "how's"


def detect(message: str) -> str | None:
    """'greet' | 'how' | 'thanks' | 'bye' | 'identity' | 'help', or None for anything else (a search or a question)."""
    text = _PUNCT.sub(" ", message.replace("’", "'")).strip()
    text = re.sub(r"[\U0001F300-\U0001FAFF☀-➿]", "", text).strip()  # emoji like a wave
    if not text or len(text.split()) > 8:
        return None
    for kind, rx in PATTERNS:
        if rx.match(text):
            return kind
    return None


CAN_DO = ("I find your photos, videos and documents from a plain description, answer questions about what's inside your "
          "files with a link to the exact page or moment, and understand English, Hindi, Marathi, Tamil and Spanish. "
          "I only work with the files in your own library.")
EXAMPLES = 'Try "beach photos from Goa" or "what does my rental agreement say about the deposit?"'

REPLIES = {
    "en": {
        "greet": "Hi{name}! I'm Memory Search, your personal memory assistant. What would you like to find today? " + EXAMPLES,
        "how": "I'm doing well, thanks for asking. What would you like to find in your library today?",
        "thanks": "You're welcome. Is there anything else you'd like me to find?",
        "bye": "Bye for now{name}. Your library will be right here when you need it.",
        "identity": "I'm Memory Search, your personal memory assistant. " + CAN_DO,
        "help": CAN_DO + " " + EXAMPLES,
    },
    "hi": {
        "greet": "नमस्ते{name}! मैं Memory Search हूँ, आपका निजी मेमोरी असिस्टेंट। आज आप क्या ढूँढना चाहेंगे? जैसे \"गोवा की बीच फ़ोटो\" या \"मेरे किराये के अनुबंध में जमा राशि कितनी है?\"",
        "how": "मैं ठीक हूँ, पूछने के लिए धन्यवाद। आज आप अपनी लाइब्रेरी में क्या ढूँढना चाहेंगे?",
        "thanks": "आपका स्वागत है। क्या मैं कुछ और ढूँढूँ?",
        "bye": "फिर मिलेंगे{name}। आपकी लाइब्रेरी यहीं रहेगी।",
        "identity": "मैं Memory Search हूँ, आपका निजी मेमोरी असिस्टेंट। मैं आपकी फ़ोटो, वीडियो और दस्तावेज़ उनके वर्णन से ढूँढता हूँ और आपकी फ़ाइलों में लिखी बातों के बारे में सवालों के जवाब देता हूँ। मैं सिर्फ़ आपकी अपनी लाइब्रेरी की फ़ाइलों के साथ काम करता हूँ।",
        "help": "मैं आपकी फ़ोटो, वीडियो और दस्तावेज़ उनके वर्णन से ढूँढता हूँ और आपकी फ़ाइलों के बारे में सवालों के जवाब देता हूँ, सही पेज या पल के लिंक के साथ। जैसे \"गोवा की बीच फ़ोटो\" लिखकर देखें।",
    },
}


def reply(kind: str, lang: str = "en", name: str | None = None) -> str:
    """Fixed persona reply, used when no language model is available (or it fails)."""
    t = REPLIES.get((lang or "en")[:2], REPLIES["en"])
    first = (name or "").strip().split(" ")[0]
    return t.get(kind, REPLIES["en"][kind]).replace("{name}", f" {first}" if first else "")


_ASKS_NUMBER = re.compile(r"\b(?:number|no\.?|num|digits?|nambar|नंबर|संख्या|எண்|n[uú]mero)\b", re.I)


def asks_for_number(message: str) -> bool:
    """'what is my PAN number' should see the full number; 'share my PAN card' gets it masked."""
    return bool(_ASKS_NUMBER.search(message))

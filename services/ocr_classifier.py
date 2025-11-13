import re

PROMO = ["sale", "unsubscribe", "offer", "limited time", "buy now", "subscribe", "promo", "discount"]
OFFICIAL = ["invoice", "amount due", "contract", "legal", "bank", "payment", "statement", "due date"]

def classify_text(text: str) -> str:
    t = text.lower()
    if any(w in t for w in OFFICIAL):
        return "official"
    if any(w in t for w in PROMO):
        return "ad"
    return "other"

def extract_unsubscribe(text: str):

    normalized = text.replace("\n", " ").replace("\r", " ")

    m = re.search(r"mailto:([\w\.\-+@]+)", normalized, re.IGNORECASE)
    if m:
        return {"type": "email", "value": m.group(1)}

    email_fallback = re.search(
        r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
        normalized
    )
    if email_fallback:
        return {"type": "email", "value": email_fallback.group(1)}

    m = re.search(r"(https?://[^\s,]+)", normalized, re.IGNORECASE)
    if m:
        return {"type": "url", "value": m.group(1)}

    return None
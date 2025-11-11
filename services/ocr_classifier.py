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
    m = re.search(r"mailto:([\w\.\-+@]+)", text)
    if m:
        return {"type":"email", "value":m.group(1)}
    m = re.search(r"(https?://[^\s,]+)", text)
    if m:
        return {"type":"url", "value":m.group(1)}
    return None
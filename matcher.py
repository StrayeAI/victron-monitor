from __future__ import annotations
from rapidfuzz import fuzz

ACCESSORY_TERMS = {
    "wall", "mount", "veggfeste", "adapter", "adaptor", "cable", "kabel",
    "cover", "deksel", "bracket", "holder", "panel", "ramme", "feste",
    "boltsett", "bolt", "bolter", "skrue", "skruer", "screw", "screws",
}

def canon(name: str) -> str:
    text = name.lower()
    for word in ["victron", "energy", "lader", "batterilader", "smart", "mk2", "med", "bluetooth"]:
        text = text.replace(word, " ")
    return " ".join(text.split())

def token_overlap(a: str, b: str) -> int:
    return len(set(canon(a).split()) & set(canon(b).split()))

def tokens(name: str) -> set[str]:
    return set(canon(name).replace("-", " ").split())

def accessory_tokens(name: str) -> set[str]:
    t = tokens(name)
    # Treat English/Norwegian terms as the same accessory family where useful.
    out = t & ACCESSORY_TERMS
    if "veggfeste" in t:
        out.update({"wall", "mount"})
    if {"wall", "mount"} <= t:
        out.add("veggfeste")
    if "boltsett" in t:
        out.update({"bolt", "bolter"})
    return out

def score(a: str, b: str) -> float:
    return float(fuzz.token_set_ratio(canon(a), canon(b)))

def safe_match(source: dict, candidate: dict) -> bool:
    sc = set(source.get("codes", []))
    cc = set(candidate.get("codes", []))
    if sc and cc:
        return bool(sc & cc)

    # Do not match accessories against the main product just because the names
    # are similar. Example: "GX Touch 50 Wall Mount" is not "GX Touch 50".
    sa = accessory_tokens(source["name"])
    ca = accessory_tokens(candidate["name"])
    if bool(sa) != bool(ca):
        return False
    if sa and ca and not (sa & ca):
        return False

    return token_overlap(source["name"], candidate["name"]) >= 1 and score(source["name"], candidate["name"]) >= 75

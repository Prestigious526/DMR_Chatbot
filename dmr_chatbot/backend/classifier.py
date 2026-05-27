"""
classifier.py  —  Tier 1
------------------------
Keyword-based fault classifier for the DMR HHPC Fault Diagnosis System.

Maps free-text symptom descriptions to one of 5 structured procedures
(P1-P5) encoded in procedures.json.

Returns:
  - Ranked list of (procedure_id, confidence 0-1, matched_keywords)
  - Escalation flag: if best confidence < THRESHOLD -> push to Tier 2 RAG

No external dependencies.
"""

from __future__ import annotations
import os, re
from dataclasses import dataclass, field

# Confidence below this -> escalate to Tier 2 (RAG + LLM)
ESCALATION_THRESHOLD = float(os.getenv("TIER1_CONFIDENCE_THRESHOLD", "0.3"))

KEYWORD_CORPUS: dict[str, list[tuple[str, float]]] = {
    "P1": [
        ("dead", 1.0), ("won't turn on", 2.5), ("wont turn on", 2.5),
        ("not turning on", 2.0), ("does not turn on", 2.0), ("no power", 1.5),
        ("doesn't start", 1.5), ("wont start", 1.5), ("blank screen", 1.5),
        ("nothing happens", 1.5), ("completely unresponsive", 2.0),
        ("won't switch on", 2.0), ("no response on power", 2.5),
        ("not booting", 1.5), ("won't boot", 1.5), ("power up problem", 2.0),
        ("battery issue", 1.2), ("no display at all", 2.0), ("unit is dead", 2.5),
        ("radio dead", 2.0), ("lifeless", 1.0), ("tp34", 2.0), ("tp 34", 2.0),
        ("u24", 2.0), ("u29", 2.0), ("r55", 1.5),
    ],
    "P2": [
        ("bite", 3.0), ("ibite", 3.0), ("ibit", 2.5), ("self test", 2.0),
        ("self-test", 2.0), ("built in test", 2.0), ("built-in test", 2.0),
        ("internal diagnostic", 2.5), ("module check", 2.0), ("module fault", 2.0),
        ("bb ok", 3.0), ("rf ok", 3.0), ("bb:ok", 3.0), ("rf:ok", 3.0),
        ("f:1", 3.0), ("s:1", 3.0), ("r:1", 3.0), ("fpga", 2.0),
        ("spi flash", 2.0), ("sm card", 2.0), ("rtc", 1.5),
        ("real time clock", 1.5), ("health check", 1.5), ("system check", 1.5),
    ],
    "P3": [
        ("display problem", 2.0), ("screen problem", 2.0),
        ("keypad not working", 2.5), ("keys not working", 2.5),
        ("key not working", 2.0), ("garbled characters", 2.5),
        ("missing characters", 2.5), ("wrong characters", 2.0),
        ("screen flickering", 2.0), ("blank display", 2.0),
        ("lcd problem", 2.0), ("keypad issue", 2.0),
        ("button not working", 2.0), ("digit wrong", 2.0),
        ("display cable", 2.0), ("backlight issue", 1.5),
        ("keyboard", 1.0), ("keypad", 1.5), ("display", 1.0), ("screen", 1.0),
    ],
    "P4": [
        ("no reception", 2.5), ("no receive", 2.5), ("can't receive", 2.5),
        ("cannot receive", 2.5), ("not receiving", 2.0),
        ("no incoming audio", 2.5), ("no sound on receive", 3.0),
        ("can't hear incoming", 2.5), ("sinad", 2.5), ("bad sinad", 3.0),
        ("no rssi", 2.5), ("rssi not showing", 2.5),
        ("no audio on receive", 3.0), ("speaker not working", 2.0),
        ("no audio", 1.5), ("no sound", 1.5), ("mute on receive", 2.5),
        ("tcxo", 2.5), ("local oscillator", 2.5), ("l.o.", 2.0),
        ("c21", 2.0), ("c114", 2.0), ("l37", 1.5), ("u21", 1.5),
        ("u4", 1.2), ("u38", 1.5), ("rx path", 2.5),
        ("receiver fault", 2.5), ("receive problem", 2.0),
        ("weak reception", 2.0), ("poor reception", 2.0),
    ],
    "P5": [
        ("no transmit", 2.5), ("can't transmit", 2.5), ("cannot transmit", 2.5),
        ("not transmitting", 2.0), ("ptt not working", 3.0),
        ("push to talk not working", 3.0), ("ptt problem", 2.5),
        ("ptt issue", 2.5), ("red led not glowing", 3.0),
        ("led not lighting", 2.5), ("tx not working", 3.0),
        ("no outgoing audio", 2.5), ("other side can't hear", 2.5),
        ("radio check fails", 2.5), ("voice not going out", 2.5),
        ("no transmission", 2.5), ("transmission problem", 2.0),
        ("sw5", 2.0), ("sw 5", 2.0), ("r248", 2.0), ("r179", 2.0),
        ("l42", 2.0), ("tx path", 2.5), ("transmitter fault", 2.5),
        ("rf power", 1.5), ("ptt", 2.0),
    ],
}

PROC_NAMES: dict[str, str] = {
    "P1": "Dead Unit",
    "P2": "BITE / Module Check",
    "P3": "Display / Keypad",
    "P4": "Receiver (Rx) Path",
    "P5": "Transmitter (Tx) Path",
}


@dataclass
class ClassifierResult:
    procedure_id: str
    procedure_name: str
    confidence: float
    matched_keywords: list[str] = field(default_factory=list)


@dataclass
class ClassifierOutput:
    results: list[ClassifierResult]
    escalate: bool      # True -> Tier 2 RAG should handle this
    raw_text: str


def _normalise(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s:.]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def classify(text: str, top_n: int = 3) -> ClassifierOutput:
    """
    Classify a free-text symptom description.
    Returns ClassifierOutput with ranked matches and escalation flag.
    """
    norm = _normalise(text)
    scores: dict[str, float] = {}
    matched: dict[str, list[str]] = {}

    for proc_id, kw_list in KEYWORD_CORPUS.items():
        score = 0.0
        hits: list[str] = []
        for phrase, weight in kw_list:
            if phrase in norm:
                score += len(phrase.split()) * weight
                hits.append(phrase)
        scores[proc_id] = score
        matched[proc_id] = hits

    scored = [(pid, s) for pid, s in scores.items() if s > 0]
    if not scored:
        return ClassifierOutput(results=[], escalate=True, raw_text=text)

    max_score = max(s for _, s in scored)
    results = []
    for pid, score in sorted(scored, key=lambda x: x[1], reverse=True)[:top_n]:
        conf = round(score / max_score, 3)
        results.append(ClassifierResult(
            procedure_id=pid,
            procedure_name=PROC_NAMES.get(pid, pid),
            confidence=conf,
            matched_keywords=matched[pid],
        ))

    escalate = not results or results[0].confidence < ESCALATION_THRESHOLD
    return ClassifierOutput(results=results, escalate=escalate, raw_text=text)


YES_TOKENS = frozenset([
    "yes", "y", "yeah", "yep", "yup", "correct", "true", "ok", "okay",
    "confirmed", "affirmative", "positive", "pass", "present", "right",
    "sure", "absolutely", "definitely", "aye",
])
NO_TOKENS = frozenset([
    "no", "n", "nope", "nah", "negative", "absent", "wrong", "incorrect",
    "missing", "fail", "failed", "false", "not", "none", "never",
])

def parse_yes_no(text: str) -> str | None:
    tokens = set(re.findall(r"\b\w+\b", text.lower()))
    is_yes = bool(tokens & YES_TOKENS)
    is_no  = bool(tokens & NO_TOKENS)
    if is_yes and not is_no:
        return "yes"
    if is_no and not is_yes:
        return "no"
    return None


if __name__ == "__main__":
    tests = [
        "radio won't turn on",
        "no audio when receiving",
        "ptt not working, red led doesn't glow",
        "garbled characters on display",
        "bite check failing",
        "what is the frequency range of this radio",
        "how do I enable lone worker mode",
        "what encryption does the secure hhpc use",
    ]
    print("=" * 65)
    for inp in tests:
        out = classify(inp)
        flag = "ESCALATE->RAG" if out.escalate else "TIER 1 OK"
        print(f"\n[{flag}] {inp!r}")
        for r in out.results:
            print(f"  [{r.procedure_id}] {r.procedure_name:<25} {r.confidence:.2f}  {r.matched_keywords[:3]}")
    print("=" * 65)

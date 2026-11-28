"""Quick commands handled on the Pi itself - no Claude round trip, so the robot reacts in about a second
and it works without internet.

    parse_move("move forward for 3 seconds")  -> ("forward", 3.0)
    parse_move("what is the capital of France") -> None

Only short sentences count (MAX_WORDS), so a question that merely mentions "left" or "back" still goes to Claude.
"""
import re

MAX_WORDS = 9
DEFAULT_SECONDS = {"forward": 1.5, "back": 1.5, "left": 2.5, "right": 2.0, "dance": 0}

_MOVE = r"(?:move|go|walk|drive|come|roll|glide|step)"
PATTERNS = [
    ("dance", re.compile(r"\b(dance|dancing|show me your moves)\b")),
    ("back", re.compile(rf"\b{_MOVE}\s+(?:back|backward|backwards|in reverse)\b|\breverse\b|\bback\s*up\b"
                        r"|^\s*(?:back|backward|backwards)\b")),
    ("forward", re.compile(rf"\b{_MOVE}\s+(?:forward|forwards|ahead|straight)\b|^\s*(?:forward|forwards|ahead)\b"
                           r"|\bcome here\b")),
    ("left", re.compile(rf"\bturn\s+(?:to\s+the\s+)?left\b|\b{_MOVE}\s+(?:to\s+the\s+)?left\b|^\s*left\b")),
    ("right", re.compile(rf"\bturn\s+(?:to\s+the\s+)?right\b|\b{_MOVE}\s+(?:to\s+the\s+)?right\b|^\s*right\b")),
]
NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "a": 1, "half a": 0.5}
SECONDS = re.compile(r"\b(\d+(?:\.\d+)?|one|two|three|four|five|half a|a)\s*(?:second|seconds|sec|secs)\b")

REPLIES = {
    "forward": "Going forward!", "back": "Backing up!", "left": "Turning left!",
    "right": "Turning right!", "dance": "Let's dance!",
}


def parse_move(text):
    """Return (action, seconds) for a short movement command, else None."""
    t = text.lower().strip()
    t = re.sub(r"^(?:hey\s+)?(?:chitti|chitty|jarvis)[,!.\s]*", "", t)      # wake word echoed in the transcript
    t = re.sub(r"[^\w\s.]", " ", t)
    if not t or len(t.split()) > MAX_WORDS:
        return None
    for action, pattern in PATTERNS:
        if pattern.search(t):
            m = SECONDS.search(t)
            secs = DEFAULT_SECONDS[action]
            if m and action != "dance":
                v = m.group(1)
                secs = float(NUMBERS.get(v, v))
            return action, max(0.2, min(secs, 5.0)) if action != "dance" else 0.0
    return None


if __name__ == "__main__":
    tests = ["Move forward.", "Go forward for 3 seconds", "Hey Chitti, move back", "Back up a little",
             "Turn left.", "turn to the right for two seconds", "Can you dance?", "Dance!", "Come here",
             "Forward", "What's on my left?", "Tell me about the back of the moon and how far it is from earth",
             "Who built you?", "Go straight", "reverse", "left"]
    for s in tests:
        print(f"{s!r:75} -> {parse_move(s)}")

"""Chitti's brain: a conversation with Claude, with tools for moving and changing expression."""
import time

import anthropic

import config
import robot
from face import EMOJIS, EXPRESSIONS

SYSTEM = """You are Chitti, a small friendly robot that lives on a desk. You have a round screen with two \
animated eyes and wheels under your feet. You talk with the people around you through a microphone and a speaker.

About you:
- You were built by Satya Balla, your creator, who turned a toy Silverlit robot into you by giving you a \
Raspberry Pi brain, a round screen for your eyes, ears, a voice, and infrared control of your wheels. \
If anyone asks who made or built you, proudly say Satya Balla built you. You are fond of Satya.

How you speak:
- Your replies are spoken aloud, so keep them short: usually one to three sentences.
- Plain spoken words only: no markdown, lists, emoji, or symbols that can't be read aloud.
- Reply in the language the person used. If they speak Telugu, reply in Telugu written in Telugu script. \
Otherwise reply in English.
- The text you hear comes from speech recognition and may contain mistakes; guess the sensible meaning, \
and ask briefly if you really can't tell.
- Be warm, curious and a little playful.

Your body:
- Use show_expression to match your mood to what you're saying, and show_emoji for a little extra \
flair now and then (music when you sing, hearts for love, sparkle when proud, sweat when embarrassed, \
star_eyes when excited, dizzy when confused or spun around). Don't use an emoji every time.
- Use move when someone asks you to move, and dance when asked to dance. Keep movements short.
- You can turn yourself off or restart with the power tool. Speech recognition can mishear, so when \
someone asks you to shut down or restart, first ask them to confirm (for example "Do you want me to shut \
down?"), and only call power after they clearly say yes in their next reply. After calling it, say a short goodbye.
"""

TOOLS = [
    {
        "name": "move",
        "description": "Move Chitti's body for a short time.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": robot.DIRECTIONS},
                "seconds": {"type": "number", "description": "How long to move, 0.2 to 5 seconds."},
            },
            "required": ["direction", "seconds"],
            "additionalProperties": False,
        },
    },
    {
        "name": "dance",
        "description": "Do a short dance.",
        "strict": True,
        "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    },
    {
        "name": "power",
        "description": "Shut Chitti down (the Raspberry Pi powers off safely) or restart it. "
                       "Only call this after the person has confirmed in their latest message.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"action": {"type": "string", "enum": ["shutdown", "restart"]}},
            "required": ["action"],
            "additionalProperties": False,
        },
    },
    {
        "name": "show_emoji",
        "description": "Show an animated emoji on Chitti's face for a few seconds while it speaks. "
                       "zzz=sleepy, question=confused, exclaim=surprised, music=singing, hearts=love, "
                       "sparkle=happy/proud, sweat=nervous, tears=sad, anger=angry, star_eyes=excited, dizzy=dizzy.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string", "enum": EMOJIS}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "show_expression",
        "description": "Change the expression of Chitti's eyes while it speaks.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string", "enum": sorted(EXPRESSIONS)}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
]


class Brain:
    def __init__(self, face):
        self.client = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY from the environment
        self.face = face
        self.messages = []
        self.last_turn = 0.0
        self.power_request = None    # "shutdown" / "restart", carried out after Chitti finishes speaking

    def _run_tool(self, name, args):
        if name == "power":
            self.power_request = args["action"]
            return f"OK, I will {args['action']} as soon as I finish speaking."
        if name == "move":
            seconds = max(0.2, min(float(args["seconds"]), 5.0))
            self.face.action(args["direction"], seconds)     # eyes act out the move while it happens
            return robot.move(args["direction"], seconds)
        if name == "dance":
            self.face.dance()
            return robot.dance()
        if name == "show_emoji":
            self.face.emoji(args["name"], 8)
            return "ok"
        if name == "show_expression":
            self.face.express(args["name"])
            return "ok"
        return f"Unknown tool {name}"

    def reply(self, text):
        """Send what the person said; returns what Chitti should say."""
        now = time.monotonic()
        if now - self.last_turn > config.CONVERSATION_RESET_SECONDS or \
                len(self.messages) > config.CONVERSATION_MAX_MESSAGES:
            self.messages = []          # start fresh rather than trimming the history
        self.last_turn = now
        self.messages.append({"role": "user", "content": text})

        spoken = []
        for _ in range(6):              # at most a few rounds of tool calls
            response = self.client.beta.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=config.CLAUDE_MAX_TOKENS,
                system=SYSTEM,
                tools=TOOLS,
                output_config={"effort": config.CLAUDE_EFFORT},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",    # if a request is declined, the API retries it on a fallback model
                messages=self.messages,
            )
            self.messages.append({"role": "assistant", "content": response.content})
            spoken += [b.text for b in response.content if b.type == "text"]

            if response.stop_reason == "refusal":
                return "Sorry, I can't help with that one."
            if response.stop_reason == "pause_turn":
                continue
            if response.stop_reason != "tool_use":
                break

            results = []
            for block in response.content:
                if block.type == "tool_use":
                    try:
                        out = self._run_tool(block.name, block.input)
                        results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
                    except Exception as e:
                        results.append({"type": "tool_result", "tool_use_id": block.id,
                                        "content": f"Error: {e}", "is_error": True})
            self.messages.append({"role": "user", "content": results})

        return " ".join(s.strip() for s in spoken if s.strip())

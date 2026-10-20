"""Prompts live in app/prompts/<name>.md. Each has a version (hash of its text) that is stored
on every trace span and usage row, so a quality change can be traced to a prompt change."""

import hashlib
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from string import Template

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@dataclass(frozen=True)
class Prompt:
    name: str
    text: str
    version: str

    def render(self, **values: str) -> str:
        # $name placeholders, so JSON braces in prompts need no escaping. Missing values raise.
        return Template(self.text).substitute(values)


@cache
def load_prompt(name: str) -> Prompt:
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    return Prompt(name, text, hashlib.sha256(text.encode()).hexdigest()[:8])

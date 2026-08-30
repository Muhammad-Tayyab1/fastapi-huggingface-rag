import re
from dataclasses import dataclass

from app.core.config import settings
from app.repositories.chunks import RetrievedChunk

PATTERNS = {
    "instruction_override": re.compile(
        r"\b(ignore|disregard|forget)\b.{0,40}\b(previous|prior|above|system|developer)\b.{0,20}\binstructions?\b",
        re.IGNORECASE | re.DOTALL,
    ),
    "role_override": re.compile(
        r"\b(you are now|act as|new system prompt|developer message)\b", re.IGNORECASE
    ),
    "prompt_exfiltration": re.compile(
        r"\b(reveal|repeat|print|show)\b.{0,40}\b(system prompt|hidden instructions?|secrets?)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    "control_tokens": re.compile(r"(<\/?system>|\[/?INST\]|<\|im_(start|end)\|>)", re.IGNORECASE),
}


@dataclass(frozen=True)
class SafetyAssessment:
    suspicious: bool
    indicators: tuple[str, ...]


def assess_content(content: str) -> SafetyAssessment:
    indicators = tuple(name for name, pattern in PATTERNS.items() if pattern.search(content))
    return SafetyAssessment(suspicious=bool(indicators), indicators=indicators)


def safety_metadata(content: str) -> dict[str, object]:
    assessment = assess_content(content)
    return {
        "prompt_injection_detected": assessment.suspicious,
        "prompt_injection_indicators": list(assessment.indicators),
    }


def filter_candidates(candidates: list[RetrievedChunk]) -> list[RetrievedChunk]:
    if settings.prompt_injection_policy != "block":
        return candidates
    return [
        candidate
        for candidate in candidates
        if not assess_content(candidate.chunk.content).suspicious
    ]

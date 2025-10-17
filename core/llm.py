from __future__ import annotations
from typing import Callable, Any, Optional, List
from dataclasses import dataclass
import json
import asyncio
import re

from core.models import LogicalMessage, ScoreResult

@dataclass
class LLMPolicy:
    # reserved for future knobs (timeouts, retries, etc.)
    pass

class LLMScorer:
    """
    send_fn: async (text:str, criterion:Optional[str]) -> Union[str, dict, number-like]
      Допускаем, что модель может вернуть просто число (строкой или числом) 0..100.
      Также поддерживаем JSON {"score": 0..1|0..100, "reason": "..."}.
    """
    def __init__(self, send_fn: Callable[[str, Optional[str]], Any], policy: Optional[LLMPolicy] = None):
        self.send_fn = send_fn
        self.policy = policy or LLMPolicy()

    async def score(self, text: str, criterion: Optional[str]) -> ScoreResult:
        body = await self.send_fn(text or "", criterion)
        body = re.sub(r'^```(?:\w+)?\r?\n', '', body)
        body = re.sub(r'\r?\n```$', '', body)
        # try raw number first
        raw_score = None
        reason = None
        if isinstance(body, (int, float)):
            raw_score = float(body)
        elif isinstance(body, str):
            # может быть просто число или JSON
            s = body.strip()
            try:
                raw_score = float(s)
            except Exception:
                try:
                    data = json.loads(s)
                    raw_score, reason = _extract_score_reason(data)
                except Exception:
                    raw_score = 0.0
        elif isinstance(body, dict):
            raw_score, reason = _extract_score_reason(body)
        else:
            raw_score = 0.0
        score01 = _normalize_score_to_01(raw_score)
        return ScoreResult(score=score01, reason=reason)
       
def _extract_score_reason(data: dict) -> tuple[float, Optional[str]]:
    sc = data.get("score")
    try:
        val = float(sc)
    except Exception:
        val = 0.0
    reason = data.get("reason")
    if isinstance(reason, str) and not reason.strip():
        reason = None
    return val, reason

def _normalize_score_to_01(val: float) -> float:
    if val is None:
        return 0.0
    # если прислали 0..100 — приводим к 0..1
    if val > 1.0:
        return max(0.0, min(1.0, val / 100.0))
    return max(0.0, min(1.0, val))

async def score_logical_messages(
    scorer: "LLMScorer",
    messages: List["LogicalMessage"],
    criterion: Optional[str],
    spacing_ms: int = 100
) -> List["ScoreResult"]:
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    spacing = spacing_ms / 1000.0

    async def _score_one(lm: "LogicalMessage", i: int) -> "ScoreResult":
        # точное расписание старта вызова относительно t0
        target = t0 + i * spacing
        now = loop.time()
        if target > now:
            await asyncio.sleep(target - now)
        sr = await scorer.score(lm.text or "", criterion)
        sr.lm = lm
        return sr

    tasks = [asyncio.create_task(_score_one(lm, i)) for i, lm in enumerate(messages)]
    return await asyncio.gather(*tasks)

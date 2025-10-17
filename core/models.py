from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class RawMessage:
    id: int
    text: Optional[str] = None
    grouped_id: Optional[int] = None
    has_media: bool = False

@dataclass
class LogicalMessage:
    ids: List[int]                  # all message ids that belong to this logical post (album or single)
    text: Optional[str]             # caption/text of the logical post (None if no text)
    grouped_id: Optional[int]       # None for single, otherwise album id
    caption_src_id: Optional[int]   # which message id inside ids has the caption
    has_media: bool                 # whether there is at least one media in this logical post

@dataclass
class ScoreResult:
    score: float
    lm: Optional[LogicalMessage] = None
    reason: Optional[str] = None

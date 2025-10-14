from __future__ import annotations
from typing import List, Dict
from .models import RawMessage, LogicalMessage

def group_into_logical_messages(raws: List[RawMessage]) -> List[LogicalMessage]:
    if not raws:
        return []
    by_group: Dict[int, List[RawMessage]] = {}
    singles: List[RawMessage] = []
    for r in raws:
        if r.grouped_id:
            by_group.setdefault(r.grouped_id, []).append(r)
        else:
            singles.append(r)

    logical: List[LogicalMessage] = []

    # albums
    for gid, chunk in by_group.items():
        chunk_sorted = sorted(chunk, key=lambda x: x.id)
        caption_item = next((c for c in chunk_sorted if c.text and c.text.strip()), None)
        caption_text = caption_item.text if caption_item else None
        caption_src_id = caption_item.id if caption_item else None
        has_media = any(c.has_media for c in chunk_sorted)
        logical.append(LogicalMessage(
            ids=[c.id for c in chunk_sorted],
            text=caption_text,
            grouped_id=gid,
            caption_src_id=caption_src_id,
            has_media=has_media
        ))

    # singles
    for r in singles:
        caption_text = r.text if r.text and r.text.strip() else None
        logical.append(LogicalMessage(
            ids=[r.id],
            text=caption_text,
            grouped_id=None,
            caption_src_id=r.id if caption_text else None,
            has_media=r.has_media
        ))

    logical.sort(key=lambda lm: lm.ids[0])  # old -> new
    return logical

def slice_logical_by_offset_limit_textful(items: List[LogicalMessage], *, limit: int, offset: int) -> List[LogicalMessage]:
    if limit <= 0 or not items:
        return []
    # items are old->new; work in new->old order to interpret offset from the end
    desc = list(reversed(items))
    picked_desc: List[LogicalMessage] = []
    skipped_textful = 0
    taken_textful = 0

    for lm in desc:
        has_text = bool(lm.text and lm.text.strip())
        if has_text and skipped_textful < offset:
            skipped_textful += 1
            continue
        if has_text and taken_textful >= limit:
            continue
        picked_desc.append(lm)
        if has_text:
            taken_textful += 1
        if taken_textful >= limit:
            break

    return list(reversed(picked_desc))

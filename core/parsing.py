import re
from typing import Set, List

_RANGE_RE = re.compile(r"\s*(\d+)\s*-\s*(\d+)\s*")

def parse_index_selection(s: str, total: int) -> List[int]:
    """
    Парсим строки вида "1, 3-5,7" в индексы [0..total-1].
    Пользователь видит нумерацию с 1.
    """
    selected: Set[int] = set()
    if not s:
        return []
    chunks = [c.strip() for c in s.split(",") if c.strip()]
    for ch in chunks:
        m = _RANGE_RE.fullmatch(ch)
        if m:
            a = int(m.group(1))
            b = int(m.group(2))
            if a > b:
                a, b = b, a
            for i in range(a, b + 1):
                idx = i - 1
                if 0 <= idx < total:
                    selected.add(idx)
            continue
        # одиночное число
        if ch.isdigit():
            idx = int(ch) - 1
            if 0 <= idx < total:
                selected.add(idx)
    return sorted(selected)

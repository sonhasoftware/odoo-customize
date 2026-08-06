# -*- coding: utf-8 -*-
import re

# Dày 0.45x1220 / Dày 0.4 x 0785
_DAY_WIDTH_FULL_RE = re.compile(
    r'D[aà]y\s*([0-9]+(?:[.,][0-9]+)?)\s*[xX×]\s*([0-9]+(?:[.,][0-9]+)?)',
    re.IGNORECASE,
)
# .D0.55x1220 — D dính với độ dày (không có chữ "ày")
_DAY_WIDTH_COMPACT_RE = re.compile(
    r'(?:\.|\b)D([0-9]+(?:[.,][0-9]+)?)\s*[xX×]\s*([0-9]+(?:[.,][0-9]+)?)',
    re.IGNORECASE,
)
_HAT_NHUA_RE = re.compile(r'^\s*hạt\b', re.IGNORECASE | re.UNICODE)


def _normalize_decimal(raw):
    text = (raw or '').strip().replace(',', '.')
    if not text:
        return ''
    try:
        val = float(text)
    except ValueError:
        return text
    if val == int(val):
        return str(int(val))
    return ('%.4f' % val).rstrip('0').rstrip('.')


def _extract_day_width(text):
    for pattern in (_DAY_WIDTH_FULL_RE, _DAY_WIDTH_COMPACT_RE):
        match = pattern.search(text)
        if match:
            return (
                _normalize_decimal(match.group(1)),
                _normalize_decimal(match.group(2)),
                text[:match.start()].rstrip('. '),
            )
    return '', '', text


def parse_ten_nvl_specs(ten_nvl, nhom=None):
    """Bóc Chất liệu / Độ bóng / Độ dày / Khổ rộng từ tên NVL (Inox cuộn).

    Hạt nhựa và NVL nhựa dạng hạt: không bóc — trả về rỗng.
    """
    empty = {
        'chat_lieu': '',
        'do_bong': '',
        'do_day': '',
        'kho_rong': '',
    }
    text = (ten_nvl or '').strip()
    if not text:
        return empty

    if nhom == 'nhua' or _HAT_NHUA_RE.search(text):
        return empty

    do_day, kho_rong, head = _extract_day_width(text)

    parts = [p.strip() for p in head.split('.') if p.strip()]
    chat_lieu = ''
    do_bong = ''
    if len(parts) >= 2:
        chat_lieu = parts[-2]
        do_bong = parts[-1]
    elif len(parts) == 1:
        chat_lieu = parts[0]

    return {
        'chat_lieu': chat_lieu,
        'do_bong': do_bong,
        'do_day': do_day,
        'kho_rong': kho_rong,
    }

# -*- coding: utf-8 -*-
import re

_DAY_WIDTH_RE = re.compile(
    r'D[aà]y\s*([0-9]+(?:[.,][0-9]+)?)\s*[xX×]\s*([0-9]+(?:[.,][0-9]+)?)',
    re.IGNORECASE,
)


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


def parse_ten_nvl_specs(ten_nvl):
    """Bóc Chất liệu / Độ bóng / Độ dày / Khổ rộng từ tên NVL."""
    empty = {
        'chat_lieu': '',
        'do_bong': '',
        'do_day': '',
        'kho_rong': '',
    }
    text = (ten_nvl or '').strip()
    if not text:
        return empty

    do_day = ''
    kho_rong = ''
    m_day = _DAY_WIDTH_RE.search(text)
    if m_day:
        do_day = _normalize_decimal(m_day.group(1))
        kho_rong = _normalize_decimal(m_day.group(2))
        head = text[:m_day.start()].rstrip('. ')
    else:
        head = text

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

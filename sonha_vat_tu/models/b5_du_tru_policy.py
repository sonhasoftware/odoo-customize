# -*- coding: utf-8 -*-
"""Chính sách B5 (dự trữ, đặt mua chốt, MOQ) theo mã công ty SX."""

DU_TRU_BNH = 'bnh'
DU_TRU_MANUAL = 'manual'
DU_TRU_TM_AVG = 'tm_avg'

CHOT_AUTO = 'auto'
CHOT_MANUAL = 'manual'

_B5_DEFAULT = {
    'du_tru': DU_TRU_BNH,
    'chot': CHOT_AUTO,
    'moq_from_chot': True,
}

B5_COMPANY_RULES = {
    'NAN': {
        'du_tru': DU_TRU_MANUAL,
        'chot': CHOT_AUTO,
        'moq_from_chot': True,
    },
    'TM2': {
        'du_tru': DU_TRU_MANUAL,
        'chot': CHOT_AUTO,
        'moq_from_chot': True,
    },
    'TM': {
        'du_tru': DU_TRU_TM_AVG,
        'chot': CHOT_MANUAL,
        'moq_from_chot': False,
    },
}


def _b5_rule(company_code):
    code = (company_code or '').strip().upper()
    rule = dict(_B5_DEFAULT)
    rule.update(B5_COMPANY_RULES.get(code, {}))
    return rule


def b5_du_tru_formula(company_code):
    return _b5_rule(company_code)['du_tru']


def b5_du_tru_is_manual(company_code):
    return b5_du_tru_formula(company_code) == DU_TRU_MANUAL


def b5_chot_is_manual(company_code):
    return _b5_rule(company_code)['chot'] == CHOT_MANUAL


def b5_moq_from_chot(company_code):
    return _b5_rule(company_code)['moq_from_chot']


def b5_plan_recompute_fields(company_code):
    """Cột B5 được ghi đè khi tính lại kế hoạch (chốt TM giữ nguyên)."""
    fields = (
        'tong_vt_can_dung',
        'tong_hang_di_duong',
        'sl_du_tru_toi_thieu',
        'sl_dat_mua_de_xuat',
    )
    if not b5_chot_is_manual(company_code):
        fields += ('sl_dat_mua_chot',)
    fields += ('sl_can_mua_theo_moq',)
    return fields

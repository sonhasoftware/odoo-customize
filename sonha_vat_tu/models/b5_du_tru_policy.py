# -*- coding: utf-8 -*-
"""Chính sách cột Dự trữ tối thiểu đơn vị (B5) theo mã công ty SX."""

DU_TRU_MODE_AUTO = 'auto'
DU_TRU_MODE_MANUAL = 'manual'

# Mỗi công ty một mode;
B5_DU_TRU_POLICIES = {
    'BNH': {'mode': DU_TRU_MODE_AUTO},
    'NAN': {'mode': DU_TRU_MODE_MANUAL},
    'TM2': {'mode': DU_TRU_MODE_MANUAL},
}

_DEFAULT_POLICY = {'mode': DU_TRU_MODE_AUTO}


def b5_du_tru_policy(company_code):
    code = (company_code or '').strip().upper()
    return B5_DU_TRU_POLICIES.get(code, _DEFAULT_POLICY)


def b5_du_tru_is_manual(company_code):
    return b5_du_tru_policy(company_code)['mode'] == DU_TRU_MODE_MANUAL


def b5_du_tru_is_auto(company_code):
    return not b5_du_tru_is_manual(company_code)

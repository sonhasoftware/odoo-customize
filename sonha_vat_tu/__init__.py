# -*- coding: utf-8 -*-
from . import models
from . import wizard
from . import controllers


def post_init_hook(env):
    from odoo.addons.sonha_vat_tu.models.bao_cao_dinh_muc_vt_tb import (
        _post_init_drop_dmtb_nhom_bao_cao,
    )
    _post_init_drop_dmtb_nhom_bao_cao(env.cr)
    env.registry.clear_cache()

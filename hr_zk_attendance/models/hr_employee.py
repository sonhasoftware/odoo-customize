# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployee(models.Model):
    """Inherit the model to add field"""
    _inherit = 'hr.employee'

    device_id_num = fields.Char(string='Mã chấm công',
                                help="Give the biometric device id", required=True)

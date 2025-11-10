from odoo import api, fields, models, _

import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError


class DKXuLy(models.Model):
    _name = 'dk.xu.ly'
    _rec_name = 'ten'

    ma = fields.Char(string="Mã", store=True)
    ten = fields.Char(string="Tên", store=True)
    stt = fields.Integer(string="Số thứ tự", store=True)

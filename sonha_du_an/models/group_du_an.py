from datetime import timedelta

from odoo import api, fields, models


class GroupDuAn(models.Model):
    _name = 'group.du.an'

    ma = fields.Char("Mã")
    ten = fields.Char("Tên")

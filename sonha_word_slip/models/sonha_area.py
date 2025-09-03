from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta


class SonhaArea(models.Model):
    _name = 'sonha.area'

    area = fields.Char(string="Khu vực")
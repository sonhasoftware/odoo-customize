from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta


class SonhaYard(models.Model):
    _name = 'sonha.yard'

    area = fields.Many2one('sonha.area', string="Khu vực")
    yard = fields.Char(string="Sân")
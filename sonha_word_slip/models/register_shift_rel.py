from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class RegisterShiftRel(models.Model):
    _name = 'register.shift.rel'

    date = fields.Date("Ngày")
    shift = fields.Many2one('config.shift', string="Ca")
    register_shift = fields.Many2one('register.shift')

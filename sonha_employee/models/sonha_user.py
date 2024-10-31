from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SonHaResUser(models.Model):
    _inherit = 'res.users'

    # def create(self, vals):
    #     res = super(SonHaResUser, self).create(vals)
    #     res.action_create_employee()
    #     return res
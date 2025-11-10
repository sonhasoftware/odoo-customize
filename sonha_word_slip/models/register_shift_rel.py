from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class RegisterShiftRel(models.Model):
    _name = 'register.shift.rel'

    date = fields.Date("Ngày")
    shift = fields.Many2one('config.shift', string="Ca")
    register_shift = fields.Many2one('register.shift')
    company_id = fields.Many2one('res.company', string="Công ty", required=True, default=lambda self: self.env.company)

    def unlink(self):
        for r in self:
            self.env['rel.ca'].sudo().search([('key', '=', r.id)]).unlink()
        return super(RegisterShiftRel, self).unlink()

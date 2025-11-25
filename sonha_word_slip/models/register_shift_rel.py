from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class RegisterShiftRel(models.Model):
    _name = 'register.shift.rel'

    date = fields.Date("Ngày")
    shift = fields.Many2one('config.shift', string="Ca")
    register_shift = fields.Many2one('register.shift')
    company_id = fields.Many2one('res.company', string="Công ty", required=True, default=lambda self: self.env.company)

    def create(self, vals):
        rec = super(RegisterShiftRel, self).create(vals)
        if rec.register_shift and rec.register_shift.employee_id:
            self.env['employee.attendance.v2'].sudo().recompute_for_employee(
                rec.register_shift.employee_id, rec.date, rec.date
            )
        return rec

    def write(self, vals):
        res = super(RegisterShiftRel, self).write(vals)
        for rec in self:
            if rec.register_shift.employee_id:
                self.env['employee.attendance.v2'].sudo().recompute_for_employee(
                    rec.register_shift.employee_id, rec.date, rec.date
                )
        return res

    def unlink(self):
        for rec in self:
            if rec.register_shift.employee_id:
                self.env['employee.attendance.v2'].sudo().recompute_for_employee(
                    rec.register_shift.employee_id, rec.date, rec.date
                )
                self.env['rel.ca'].sudo().search([('key', '=', rec.id)]).unlink()
        return super(RegisterShiftRel, self).unlink()

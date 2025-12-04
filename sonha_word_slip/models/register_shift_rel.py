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
        for r in rec:
            if r.register_shift and r.register_shift.employee_id:
                self.env['employee.attendance.v2'].sudo().recompute_for_employee(
                    r.register_shift.employee_id, r.date, r.date
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
    @api.constrains('date')
    def validate_register_shift_date(self):
        for r in self:
            register_shift = self.env['register.shift'].sudo().search([('employee_id', '=', r.register_shift.employee_id.id),
                                                                       ('id', '!=', r.register_shift.id)])
            list_date = register_shift.mapped('register_rel')
            for rec in list_date:
                if rec.date == r.date:
                    date = r.date.strftime('%d/%m/%Y')
                    raise ValidationError(f"Bạn đã có đơn đổi ca cho ngày {date} rồi!")
            form = self.env['register.shift.rel'].sudo().search([('register_shift', '=', r.register_shift.id),
                                                                 ('id', '!=', r.id)])
            for rec in form:
                if rec.date == r.date:
                    date = r.date.strftime('%d/%m/%Y')
                    raise ValidationError(f"Bạn đã có đơn đổi ca cho ngày {date} rồi!")

    def unlink(self):
        for rec in self:
            if rec.register_shift.employee_id:
                self.env['employee.attendance.v2'].sudo().recompute_for_employee(
                    rec.register_shift.employee_id, rec.date, rec.date
                )
                self.env['rel.ca'].sudo().search([('key', '=', rec.id)]).unlink()
        return super(RegisterShiftRel, self).unlink()

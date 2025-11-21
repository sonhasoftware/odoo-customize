from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class RegisterShiftRel(models.Model):
    _name = 'register.shift.rel'

    date = fields.Date("Ngày")
    shift = fields.Many2one('config.shift', string="Ca")
    register_shift = fields.Many2one('register.shift')
    company_id = fields.Many2one('res.company', string="Công ty", required=True, default=lambda self: self.env.company)

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
        for r in self:
            self.env['rel.ca'].sudo().search([('key', '=', r.id)]).unlink()
        return super(RegisterShiftRel, self).unlink()

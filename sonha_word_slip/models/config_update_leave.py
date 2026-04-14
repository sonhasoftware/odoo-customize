from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, time, timedelta


class ConfigUpdateLeave(models.Model):
    _name = 'config.update.leave'

    employee_id = fields.Many2one('hr.employee', string="Nhân viên", required=True, store=True)
    amount_leave_balance = fields.Integer(string="Số phép", store=True)
    date = fields.Date(string="Ngày", default=fields.Date.context_today, store=True)
    key = fields.Many2one('rel.don.tu', store=True)

    @api.constrains('amount_leave_balance')
    def validate_amount_leave_balance(self):
        for r in self:
            if r.amount_leave_balance < 1:
                raise ValidationError("Số phép thêm phải lớn hơn hoặc bằng 1!")

    def create(self, vals):
        res = super(ConfigUpdateLeave, self).create(vals)
        update = self.env['rel.don.tu'].sudo().create({
            'employee_id': res.employee_id.id,
            'type_leave': 1,
            'key_type_leave': 'NP',
            'date': res.date,
            'leave_more': res.amount_leave_balance,
            'status': 'done',
        })
        res.sudo().write({'key': update.id})
        return res

    def unlink(self):
        for r in self:
            self.env['rel.don.tu'].sudo().search([('id', '=', r.key.id)]).unlink()
        return super(ConfigUpdateLeave, self).unlink()


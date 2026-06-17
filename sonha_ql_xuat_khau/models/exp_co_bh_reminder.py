from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class ExpCoBhReminder(models.Model):
    _name = 'exp.co.bh.reminder'

    remind_type = fields.Selection([('co', "CO"), ('bh', "BH")],
                                   string="Loại", required=True, store=True)
    is_active = fields.Boolean(string="Được sử dụng", store=True)
    noti_day = fields.Integer(string="Nhắc mail sau (ngày)", store=True)

    @api.constrains('remind_type', 'is_active')
    def validate_active_reminder(self):
        for r in self:
            other_reminder = self.sudo().search([('id', '!=', r.id),
                                                 ('remind_type', '=', r.remind_type),
                                                 ('is_active', '=', True)])
            if r.is_active and other_reminder:
                raise ValidationError("Đã có một lịch nhắc cùng loại được sử dụng rồi!")

    @api.constrains('noti_day')
    def validate_noti_day(self):
        for r in self:
            if r.noti_day < 1:
                raise ValidationError("Số ngày phải lớn hơn 0!")

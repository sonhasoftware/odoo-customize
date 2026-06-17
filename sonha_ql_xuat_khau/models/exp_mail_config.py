from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class ExpMailConfig(models.Model):
    _name = 'exp.mail.config'

    code = fields.Char(string="Mã", store=True)
    name = fields.Char(string="Tên", store=True)
    mail_to = fields.Many2many('hr.employee', 'rel_exp_mail_to_employee',
                               'exp_mail', 'employee_id', string="Người nhận mail (Hệ thống)", store=True)
    mail_to_char = fields.Char(string="Người nhận mail (Ngoài hệ thống)", store=True)
    mail_cc = fields.Many2many('hr.employee', 'rel_exp_mail_cc_employee',
                               'exp_mail', 'employee_id', string="Người được cc (Hệ thống)", store=True)
    mail_cc_char = fields.Char(string="Người được cc (Ngoài hệ thống)", store=True)
    default_rule = fields.Many2one('exp.state.transition.rule', string="Quy tắc mặc định", store=True)

    @api.constrains('default_rule')
    def _validate_default_rule(self):
        for r in self:
            records = self.sudo().search([('default_rule', '=', r.default_rule.id),
                                          ('id', '!=', r.id)])
            if records:
                raise ValidationError("Đã có một dòng có quy tắc mặc định này rồi!")

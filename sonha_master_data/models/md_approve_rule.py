from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class MDApproveRule(models.Model):
    _name = 'md.approve.rule'

    model_apply = fields.Many2one('ir.model', string="Áp dụng", required=True, ondelete='cascade')
    company_ids = fields.Many2many('res.company', string="Đơn vị", required=True)
    step = fields.One2many('md.approve.step', 'approve_rule', string="Quy trình duyệt")

    @api.constrains('company_ids', 'model_apply')
    def validate_duplicate_company(self):
        for r in self:
            rule = self.env['md.approve.rule'].sudo().search([('id', '!=', r.id),
                                                              ('company_ids', 'in', r.company_ids.ids),
                                                              ('model_apply', '=', r.model_apply.id)])
            if rule:
                raise ValidationError("Một công ty chỉ được gắn với 1 luồng duyệt!")

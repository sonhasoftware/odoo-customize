from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class ExpStateTransitionRule(models.Model):
    _name = 'exp.state.transition.rule'
    _rec_name = 'transition_name'

    from_state_id = fields.Many2one('exp.contract.state', string="Từ trạng thái", required=True, store=True)
    from_state_domain = fields.Binary(compute="_compute_from_state_domain")
    to_state_id = fields.Many2one('exp.contract.state', string="Đến trạng thái", required=True, store=True)
    to_state_domain = fields.Binary(compute="_compute_to_state_domain")
    required_document = fields.Boolean(string="Có cần chứng từ đính kèm không", required=True, store=True)
    required_payment = fields.Boolean(string="Có cần thanh toán không", required=True, store=True)
    note = fields.Text(string="Ghi chú", store=True)
    transition_name = fields.Char(string="Tên chuyển trạng thái", compute="get_name", store=True)

    @api.depends('from_state_id.name', 'to_state_id.name')
    def get_name(self):
        for r in self:
            if r.from_state_id.name and r.to_state_id.name:
                r.transition_name = f"{r.from_state_id.name} → {r.to_state_id.name}"
            else:
                r.transition_name = ""

    @api.constrains('from_state_id', 'to_state_id')
    def validate_transition_rule(self):
        for r in self:
            list_rule = self.env['exp.state.transition.rule'].sudo().search([('id', '!=', r.id)])
            list_from = list_rule.mapped('from_state_id')
            list_to = list_rule.mapped('to_state_id')
            if list_rule and r.from_state_id and r.to_state_id and r.from_state_id not in list_to and r.to_state_id not in list_from:
                raise ValidationError("Chỉ được tồn tại 1 luồng trạng thái!")
            if r.from_state_id and r.from_state_id in list_from:
                raise ValidationError("Đã có quy tắc bắt đầu bằng trạng thái này rồi!")
            if r.to_state_id and r.to_state_id in list_to:
                raise ValidationError("Đã có quy tắc kết thúc bằng trạng thái này rồi!")

    @api.onchange('to_state_id')
    def _compute_from_state_domain(self):
        for r in self:
            domain = [('active', '=', True)]
            if r.to_state_id:
                pre_state_seq = r.to_state_id.sequence - 1
                domain.append(('sequence', '=', pre_state_seq))
            r.from_state_domain = domain

    @api.onchange('from_state_id')
    def _compute_to_state_domain(self):
        for r in self:
            domain = [('active', '=', True)]
            if r.from_state_id:
                next_state_seq = r.from_state_id.sequence + 1
                domain.append(('sequence', '=', next_state_seq))
            r.to_state_domain = domain















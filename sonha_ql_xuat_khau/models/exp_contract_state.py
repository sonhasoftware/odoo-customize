from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class ExpContractState(models.Model):
    _name = 'exp.contract.state'
    _order = 'sequence'

    code = fields.Char(string="Mã trạng thái", required=True, store=True)
    name = fields.Char(string="Tên trạng thái", required=True, store=True)
    sequence = fields.Integer(string="Thứ tự thực hiện", required=True, store=True)
    description = fields.Text(string="Mô tả nghiệp vụ", store=True)
    active = fields.Boolean(string="Có được sử dụng không", store=True)
    is_default = fields.Boolean(string="Trạng thái mặc định", store=True)

    @api.constrains('sequence', 'active')
    def validate_sequence(self):
        for r in self:
            other_state = self.sudo().search([('id', '!=', r.id), ('active', '=', True)])
            if r.active and r.sequence < 1:
                raise ValidationError("Trạng thái phải có thứ tự lớn hơn 0!")
            if r.sequence and r.active and r.sequence in other_state.mapped('sequence'):
                raise ValidationError("Đã có trạng thái ứng với thứ tự này rồi!")

    @api.constrains('is_default', 'active')
    def validate_default_state(self):
        for r in self:
            other_default = self.sudo().search([('id', '!=', r.id),
                                                ('active', '=', True),
                                                ('is_default', '=', True)])
            if r.active and r.is_default and other_default:
                raise ValidationError("Đã có trạng thái mặc định rồi!")

    @api.onchange('active')
    def _onchange_active(self):
        for r in self:
            if not r.active:
                r.sequence = 0

    def write(self, vals):
        res = super(ExpContractState, self).write(vals)
        if 'active' in vals:
            for r in self:
                used_contract = self.env['exp.contract'].sudo().search([('state_id', '=', r.id)])
                if used_contract:
                    raise ValidationError("Đang có hợp đồng ở trạng thái này, không thể dừng hoạt động!")
                if not r.active:
                    self.env['exp.state.transition.rule'].sudo().search(['|', ('from_state_id', '=', r.id),
                                                                         ('to_state_id', '=', r.id)]).unlink()
        return res

    def unlink(self):
        for r in self:
            if r.active:
                raise ValidationError("Không thể xóa trạng thái đang hoạt động!")
        return super(ExpContractState, self).unlink()


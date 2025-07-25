from odoo import api, fields, models


class ApprovalStatePlan(models.Model):
    _name = 'approval.state.plan'
    _description = 'Trạng thái luồng duyệt'

    name = fields.Char("Tên")
    code_state = fields.Char("Mã trạng thái")

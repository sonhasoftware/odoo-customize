from odoo import api, fields, models


class ApprovalState(models.Model):
    _name = 'approval.state'
    _description = 'Trạng thái luồng duyệt'

    name = fields.Char("Tên", required=True)
    code_state = fields.Char(string="Mã trạng thái")
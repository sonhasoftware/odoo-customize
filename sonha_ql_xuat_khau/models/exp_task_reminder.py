from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class ExpTaskReminder(models.Model):
    _name = 'exp.task.reminder'

    contract_id = fields.Many2one('exp.contract', string="Hợp đồng", required=True, store=True)
    document_type_id = fields.Many2one('exp.document.type', string="Loại chứng từ", required=True, store=True)
    due_date = fields.Date(string="Ngày cần hoàn thành", required=True, store=True)
    assigned_to = fields.Many2one('res.users', string="User được chỉ định", required=True, store=True)
    status = fields.Char(string="Trạng thái nhắc việc", required=True, store=True)



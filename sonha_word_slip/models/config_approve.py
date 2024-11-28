from odoo import api, fields, models


class ConfigApprove(models.Model):
    _name = 'config.approve'

    company_id = fields.Many2one('res.company', string="Công ty")
    department_id = fields.Many2one('hr.department', string="Phòng ban")
    approver_ids = fields.One2many('approval.workflow.step', 'workflow_id', string="Các bước duyệt")


class ApprovalWorkflowStep(models.Model):
    _name = 'approval.workflow.step'
    _description = 'Approval Workflow Step'

    workflow_id = fields.Many2one('config.approve', string="Luồng duyệt")
    leave = fields.Many2one('config.word.slip', string="Kiểu nghỉ")
    condition = fields.Char(string="Điều kiện phê duyệt", help="Điều kiện áp dụng cho bước này")
    level = fields.Integer("Cấp bậc")

    state_ids = fields.Many2many('approval.state', 'workflow_state_rel', 'workflow_id', 'state_id',
                                 string="Các trạng thái phê duyệt")


class ApprovalState(models.Model):
    _name = 'approval.state'
    _description = 'Approval State'

    name = fields.Char(string="Tên trạng thái", required=True)



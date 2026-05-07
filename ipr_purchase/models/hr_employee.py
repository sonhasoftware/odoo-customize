from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    ipr_request_ids = fields.One2many(
        'ipr.request',
        'employee_id',
        string='Lịch sử yêu cầu mua hàng',
    )
    ipr_request_count = fields.Integer(
        string='Số phiếu yêu cầu',
        compute='_compute_ipr_request_count',
    )

    def _compute_ipr_request_count(self):
        for emp in self:
            emp.ipr_request_count = self.env['ipr.request'].search_count(
                [('employee_id', '=', emp.id)]
            )

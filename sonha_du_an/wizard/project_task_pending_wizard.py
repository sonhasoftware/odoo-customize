from odoo import fields, models
from odoo.exceptions import ValidationError


class ProjectTaskPendingWizard(models.TransientModel):
    _name = 'project.task.pending.wizard'
    _description = 'Pending Task Wizard'

    task_id = fields.Many2one(
        'project.task',
        string='Nhiệm vụ',
        required=True,
        readonly=True,
    )

    ly_do_pending = fields.Text(
        string='Lý do Pending',
        required=True,
    )

    so_ngay_pending = fields.Integer(
        string='Số ngày Pending',
        required=True,
        default=1,
    )

    def action_confirm(self):
        self.ensure_one()

        if self.so_ngay_pending <= 0:
            raise ValidationError(
                'Số ngày Pending phải lớn hơn 0!'
            )

        self.task_id.write({
            'ly_do_pending': self.ly_do_pending,
            'so_ngay_pending': self.so_ngay_pending,
            'trang_thai': 'pd',
            'ngay_hoan_thanh': False,
        })

        return {
            'type': 'ir.actions.act_window_close',
        }
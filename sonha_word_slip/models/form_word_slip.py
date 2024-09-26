from odoo import api, fields, models


class FormWordSlip(models.Model):
    _name = 'form.word.slip'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    department = fields.Many2one('hr.department', string="Phòng ban", required=True, tracking=True)
    employee_id = fields.Many2one('hr.employee', string="Tên nhân viên", tracking=True)
    type = fields.Many2one('config.word.slip', "Loại đơn", tracking=True)
    word_slip_id = fields.One2many('word.slip', 'word_slip', string="Ngày", tracking=True)
    description = fields.Text("Lý do", tracking=True)
    status = fields.Selection([
        ('draft', 'Nháp'),
        ('done', 'Đã duyệt'),
    ], string='Trạng thái', tracking=True)

    @api.onchange('department')
    def _onchange_department_id(self):
        for r in self:
            if r.department:
                return {
                    'domain': {
                        'employee_id': [('department_id', '=', self.department.id)]
                    }
                }
            else:
                return {
                    'domain': {
                        'employee_id': []
                    }
                }

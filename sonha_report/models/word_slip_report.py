from odoo import models, fields, api


class WordSlipReport(models.Model):
    _name = 'word.slip.report'

    employee_ids = fields.Many2many('hr.employee', string="Tên nhân viên")
    department_id = fields.Many2one('hr.department', string="Phòng ban")
    slip_code = fields.Char("Mã đơn")
    slip_type = fields.Many2one('config.word.slip', string="Loại đơn")
    from_date = fields.Text("Từ ngày")
    to_date = fields.Text("Đến ngày")
    status = fields.Selection([('sent', "Nháp"),
                               ('draft', "Chờ duyệt"),
                               ('done', "Đã duyệt"),
                               ('cancel', "Hủy")], string="Trạng thái")
    duration = fields.Float("Số ngày nghỉ phép")
    create_employee = fields.Many2one('res.users', string="Người tạo")
    slip_create_date = fields.Datetime("Ngày tạo")

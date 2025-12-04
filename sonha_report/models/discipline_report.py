from odoo import models, api, fields


class DisciplineReport(models.Model):
    _name = 'discipline.report'

    object_discipline = fields.Many2one('object.reward.config', string="Đối tượng")
    person_discipline = fields.Char(string="Nhân viên")
    date_discipline = fields.Date('Ngày vi phạm')
    reason = fields.Char(string="Lý do kỷ luật")
    content = fields.Char(string="Nội dung kỷ luật")

    discipline_number = fields.Char(string="Số quyết định")
    state = fields.Many2one('state.reward.config', string="Trạng thái")
    form_discipline = fields.Many2one('form.reward.config', string="Hình thức kỷ luật")
    form_discipline_properties = fields.Char(string="Chế tài áp dụng")
    date_start = fields.Date("Ngày hiệu lực")
    date_end = fields.Date(string="Ngày kết thúc kỷ luật")
    date_sign = fields.Date(string="Ngày ký")
    amount = fields.Float(string="Mức bồi thường")
    option = fields.Selection([('0', 'Trừ vào lương'),
                               ('1', 'Thanh toán tiền mặt')],
                              default='1', string="Hình thức bồi thường")
    note = fields.Char(string="Chú thích")
    sign_person = fields.Many2one('hr.employee', string="Người phê duyệt")
    person_discipline_job = fields.Many2one('hr.job', string="Chức vụ")
    department_id = fields.Many2one('hr.department', string="Phòng ban")
    employee_code = fields.Char(string="Mã nhân viên")
    address = fields.Char(string="Địa chỉ làm việc")
    employee_id = fields.Many2one('hr.employee', string="Nhân viên")
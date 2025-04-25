from odoo import models, api, fields


class DismissalPerson(models.Model):
    _name = 'dismissal.person'

    object_discipline = fields.Many2one('object.reward.config', string="Đối tượng", ondelete='cascade')
    person_dismissal = fields.One2many('employee.rel', 'person_dismissal', string="Nhân viên")
    date_discipline = fields.Date('Ngày vi phạm')
    reason = fields.Char(string="Lý do")
    content = fields.Char(string="Nội dung")

    discipline_number = fields.Char(string="Số quyết định")
    state = fields.Many2one('state.reward.config', string="Trạng thái", ondelete='cascade')
    form_discipline = fields.Many2one('form.reward.config', string="Hình thức", ondelete='cascade')
    form_discipline_properties = fields.Char(string="Chế tài áp dụng")
    date_start = fields.Date("Ngày hiệu lực")
    date_end = fields.Date(string="Ngày kết thúc")
    date_sign = fields.Date(string="Ngày ký")
    note = fields.Char(string="Chú thích")
    sign_person = fields.Many2one('hr.employee', string="Người phê duyệt", ondelete='cascade')
    title_person_sign = fields.Many2one('hr.job', string="Chức vụ", compute="get_info_employee_2", store=True)
    file_desision = fields.Binary(string="Đường dẫn file QĐ")

    @api.depends('sign_person')
    def get_info_employee_2(self):
        for r in self:
            if r.sign_person:
                r.title_person_sign = r.sign_person.job_id.id if r.sign_person.job_id else None

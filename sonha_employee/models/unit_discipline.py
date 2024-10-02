from odoo import models, fields, api

class UnitDiscipline(models.Model):
    _name='unit.discipline'
    _description='Unit Discipline'
    
    object_discipline = fields.Many2one('object.reward.config', string="Đối tượng kỷ luật", ondelete='cascade')
    unit = fields.One2many('department.rel','unit_discipline', string="Đơn vị")
    report_to = fields.Many2one('hr.employee', string="Báo cáo bởi", ondelete='cascade')
    reason = fields.Char(string="Lý do kỷ luật")
    date_decipline = fields.Date(string="Ngày vi phạm")
    note = fields.Char("Chú thích")
    
    desision_number = fields.Char(string="Số quyết định")
    form_discipline = fields.Many2one('form.reward.config', string="Hình thức kỷ luật", ondelete='cascade')
    state = fields.Many2one('state.reward.config',string="Trạng thái", ondelete='cascade')
    applicable_sanctions = fields.Char(string="Chế tài áp dụng")
    date_start = fields.Date(string="Ngày bắt đầu")
    date_end = fields.Date(string="Ngày kết thúc")
    date_sign = fields.Date(string="Ngày ký")
    amount = fields.Float(string="Mức bồi thường")
    option = fields.Selection([('0', 'Trừ vào lương'), ('1', 'Thanh toán tiền mặt')], default='1', string="Hình thức bồi thường")
    note_1 = fields.Char(string="Chú thích")
    sign_person = fields.Many2one('hr.employee', string="Người phê duyệt", ondelete='cascade')
    title_person_sign = fields.Many2one('hr.job', string = "Chức vụ", compute="get_info_employee", store= True)
    file_desision = fields.Binary(string="Đường dẫn file QĐ")
    
    @api.depends('sign_person')
    def get_info_employee(self):
        for r in self:
            if r.sign_person:
                r.title_person_sign = r.sign_person.job_id.id if r.sign_person.job_id else None
    
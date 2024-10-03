from odoo import models,api,fields

class PersonDiscipline(models.Model):
    _name='person.discipline'
    _description='Person Discipline'
    
    object_discipline = fields.Many2one('object.reward.config', string="Đối tượng", ondelete='cascade')
    person_discipline = fields.One2many('employee.rel','person_discipline', string="Nhân viên")
    report_to = fields.Many2one('hr.employee', string="Báo cáo bởi", ondelete='cascade')
    date_discipline = fields.Date('Ngày vi phạm')
    reason = fields.Char(string="Lý do kỷ luật")
    content = fields.Char(string="Nội dung kỷ luật")
    
    discipline_number = fields.Char(string="Số quyết định")
    state = fields.Many2one('state.reward.config',string="Trạng thái", ondelete='cascade')
    form_discipline = fields.Many2one('form.reward.config', string="Hình thức kỷ luật", ondelete='cascade')
    form_discipline_properties = fields.Char(string="Chế tài áp dụng")
    date_start = fields.Date("Ngày hiệu lực")
    date_end = fields.Date(string="Ngày kết thúc kỷ luật")
    date_sign = fields.Date(string="Ngày ký")
    amount = fields.Float(string="Mức bồi thường", compute="total_amount")
    option = fields.Selection([('0', 'Trừ vào lương'), ('1', 'Thanh toán tiền mặt')], default='1', string="Hình thức bồi thường")
    note = fields.Char(string="Chú thích")
    sign_person = fields.Many2one('hr.employee', string="Người phê duyệt", ondelete='cascade')
    title_person_sign = fields.Many2one('hr.job', string = "Chức vụ", compute="get_info_employee_2", store= True)
    file_desision = fields.Binary(string="Đường dẫn file QĐ")
    
    @api.depends('sign_person')
    def get_info_employee_2(self):
        for r in self:
            if r.sign_person:
                r.title_person_sign = r.sign_person.job_id.id if r.sign_person.job_id else None
    
    def total_amount(self):
        for r in self:
            list_amount = self.env['employee.rel'].sudo().search([('person_discipline', '=', r.id)])
            if list_amount:
                r.amount = sum(list_amount.mapped('amount_discipline'))
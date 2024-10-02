from odoo import models,fields, api

class UnitReward(models.Model):
    _name = 'unit.reward'
    _description='Unit Reward'
    
    object_reward = fields.Many2one('object.reward.config', string="Đối tượng khen thưởng", ondelete='cascade')
    form_reward = fields.Many2one('form.reward.config', string="Hình thức khen thưởng", ondelete='cascade')
    unit = fields.One2many('department.rel','unit_reward', string="Đơn vị")
    level_reward = fields.Many2one('level.reward.config',string="Cấp khen thưởng", ondelete='cascade')
    title_reward = fields.Many2one('title.reward.config',string="Danh hiệu khen thưởng")
    reason = fields.Char(string="Lý do khen thưởng")
    amount = fields.Float(string="Mức thưởng")
    option = fields.Selection([('0', 'Cộng vào lương'), ('1', 'Nhận tiền mặt')], default='1', string="Hình thức nhận thưởng")
    note = fields.Char(string="Ghi chú")
    
    desision_number = fields.Char(string="Số quyết định")
    state = fields.Many2one('state.reward.config',string="Trạng thái", ondelete='cascade')
    effective_date = fields.Date(string="Ngày hiệu lực")
    sign_date = fields.Date(string="Ngày ký")
    sign_person = fields.Many2one('hr.employee', string="Người phê duyệt", ondelete='cascade')
    title_person_sign = fields.Many2one('hr.job', string = "Chức vụ", compute="get_info_employee_2", store= True)
    file_desision = fields.Binary(string="Đường dẫn file QĐ")
    
    @api.depends('sign_person')
    def get_info_employee_2(self):
        for r in self:
            if r.sign_person:
                r.title_person_sign = r.sign_person.job_id.id if r.sign_person.job_id else None
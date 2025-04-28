from odoo import api, fields, models

class RewardReport(models.Model):
    _name = 'reward.report'

    object_reward = fields.Many2one('object.reward.config', string="Đối tượng khen thưởng")
    person_reward = fields.Char(string="Nhân viên")
    title_reward = fields.Many2one('title.reward.config', string="Danh hiệu khen thưởng")
    form_reward = fields.Many2one('form.reward.config', string="Hình thức khen thưởng")
    level_reward = fields.Many2one('level.reward.config', string="Cấp khen thưởng")
    reason = fields.Char(string="Lý do khen thưởng")
    amount = fields.Float(string="Mức thưởng")
    option = fields.Selection([('0', 'Cộng vào lương'),
                               ('1', 'Nhận tiền mặt')],
                              default='1', string="Hình thức nhận thưởng")
    note = fields.Char(string="Nội dung khen thưởng")
    desision_number = fields.Char(string="Số quyết định")
    state = fields.Many2one('state.reward.config', string="Trạng thái")
    effective_date = fields.Date(string="Ngày hiệu lực")
    sign_date = fields.Date(string="Ngày ký")
    sign_person = fields.Many2one('hr.employee', string="Người phê duyệt")
    person_reward_job = fields.Many2one('hr.job', string="Chức vụ")
    department_id = fields.Many2one('hr.department', string="Phòng ban")
    employee_code = fields.Char(string="Mã nhân viên")
    address = fields.Char(string="Địa chỉ làm việc")

    def get_option_label(self):
        return dict(self._fields['option'].selection).get(self.option)
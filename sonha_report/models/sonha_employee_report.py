from odoo import api, fields, models


class SonhaEmployeeReport(models.Model):
    _name = 'sonha.employee.report'

    name = fields.Char(string="Tên nhân viên")
    employee_code = fields.Char(string="Mã nhân viên")
    mobile_phone = fields.Char(string="Di động")
    work_email = fields.Char(string="Email công việc")
    company_id = fields.Many2one('res.company', string="Công ty")
    department_id = fields.Many2one('hr.department', string="Phòng ban")
    job_id = fields.Many2one('hr.job', string="Chức vụ")
    parent_id = fields.Many2one('hr.employee', string="Quản lý")
    date_birthday = fields.Date("Ngày sinh")
    place_birthday = fields.Char("Nơi sinh")
    gender = fields.Selection([('male', "Nam"), ('female', "Nữ"), ('other', "Khác")], string="Giới tính")
    marital_status = fields.Selection([('single', "Độc thân"), ('married', "Đã kết hôn")], string="Tình trạng hôn nhân")
    nation = fields.Char("Dân tộc")
    religion = fields.Selection([('yes', "Có"), ('no', "Không")], string="Tôn giáo")
    tax_code = fields.Char("Mã số thuế")
    hometown = fields.Char("Quê quán")
    permanent = fields.Char("Địa chỉ thường chú")
    onboard = fields.Date("Ngày vào công ty")
    reception_date = fields.Date("Ngày tiếp nhận")
    number_cccd = fields.Char("Số CCCD")
    date_cccd = fields.Date("Ngày cấp")
    place_of_issue = fields.Char("Nơi cấp")
    culture_level = fields.Char("Trình độ văn hóa")
    total_compensatory = fields.Float("Thời gian nghỉ bù còn lại")
    old_leave_blance = fields.Float("Phép cũ")
    new_leave_balance = fields.Float("Phép mới")
    device_id_num = fields.Char("Mã chấm công")
    employee_type = fields.Selection([('employee', "Nhân viên"),
                                      ('student', "Học sinh"),
                                      ('trainee', "Thực tập sinh"),
                                      ('contractor', "Người mua"),
                                      ('freelance', "Tự do")], string="Kiểu nhân viên")
    shift = fields.Many2one('config.shift', string="Ca làm việc")
    status_employee = fields.Selection([('working', "Đang làm việc"),
                                        ('maternity_leave', "Nghỉ thai sản"),
                                        ('quit_job', 'Nghỉ việc'),
                                        ('trial', 'Thử việc')], string='Trạng thái làm việc')
    date_quit = fields.Date("Ngày nghỉ việc")
    reason_quit = fields.Char("Lý do nghỉ việc")
    seniority_display = fields.Char("Thâm niên")
    sonha_number_phone = fields.Char("Số điện thoại")
    contract_id = fields.Many2one('hr.contract', string="Hợp đồng")
    address_id = fields.Char(string="Địa chỉ làm việc")

    def get_gender_label(self):
        return dict(self._fields['gender'].selection).get(self.gender)

    def get_marital_status_label(self):
        return dict(self._fields['marital_status'].selection).get(self.marital_status)

    def get_religion_label(self):
        return dict(self._fields['religion'].selection).get(self.religion)

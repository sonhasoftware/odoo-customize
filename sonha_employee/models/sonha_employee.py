from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SonHaEmployee(models.Model):
    _inherit = 'hr.employee'
    _rec_name = 'combination'

    list_employee = fields.Many2many('hr.employee', 'ir_employee_group_rel',
                                     'employee_group_rel', 'employee_rel',
                                     string='List Staff')

    lower_grade = fields.Many2many('hr.employee', 'ir_lower_grade_id_rel',
                                   'lower_grade_id_rel', 'lower_grade_id',
                                    string="Lower Grade")

    kpi = fields.Many2many('hr.employee', 'ir_kpi_id_rel',
                           'kpi_id_rel', 'kpi_id',
                           string="Edit KPI")

    department_ids = fields.Many2many('hr.department', 'ir_department_ids_rel',
                                      'department_ids_rel', 'department_ids',
                                      string="Department")

    level = fields.Selection([
        ('N0', 'N0'),
        ('N1', 'N1'),
        ('N2', 'N2'),
        ('N3', 'N3'),
        ('N4', 'N4'),
        ('N5', 'N5'),
    ], string='Level')

    date = fields.Date('Ngày')
    number = fields.Integer('Số')
    status_employee = fields.Selection([
        ('working', "Đang làm việc"),
        ('maternity_leave', "Nghỉ thai sản"),
        ('quit_job', 'Nghỉ việc'),
        ('trial', 'Thử việc')
    ], string='Trạng thái làm việc')

    # các field page hr setting
    onboard = fields.Date('Ngày vào công ty')
    # type_contract = fields.Many2one('hr.contract', string="Loại hợp đồng")
    employee_code = fields.Char("Mã nhân viên")
    shift = fields.Many2one('config.shift')

    # các field page infomation page 1
    date_birthday = fields.Date("Ngày sinh")
    place_birthday = fields.Char("Nơi sinh")
    marital_status = fields.Char("Tình trạng hôn nhân")
    nation = fields.Char("Dân tộc")
    religion = fields.Char("Tôn giáo")
    hometown = fields.Char("Quê quán")
    permanent_address = fields.Char("Địa chỉ thường trú")
    current_residence = fields.Char("Nơi ở hiện tại")

    # các field page private infomation page 2
    number_cccd = fields.Char("Số CCCD")
    date_cccd = fields.Date("Ngày cấp")
    place_of_issue = fields.Char("Nơi cấp")
    passport_number = fields.Char("Số hộ chiếu")
    date_passport = fields.Date("Ngày hộ chiếu")
    expiration_date_passport = fields.Date("Ngày hết hạn")
    place_of_issue_passport = fields.Char("Nơi cấp hộ chiếu")
    number_visa = fields.Char("Số visa")
    date_visa = fields.Date("Ngày cấp(visa)")
    expiration_date_visa = fields.Date("Ngày hết hạn(visa)")
    place_of_issue_visa = fields.Char("Nơi cấp(visa)")
    reunion_day = fields.Date("Ngày vào Đoàn")
    place_reunion = fields.Char("Nơi vào(Đoàn)")
    fee_reunion = fields.Boolean("Đoàn phí")
    party_member_day = fields.Date("Ngày vào Đảng")
    place_party_member = fields.Char("Nơi vào Đảng")
    fee_party_member = fields.Boolean("Đảng phí")

    combination = fields.Char(string='Combination', compute='_compute_fields_combination')
    work_ids = fields.One2many('work.process', 'employee_id', string="Quá trình công tác")

    birth_month = fields.Integer(string="Sinh nhật", compute='_compute_birth_month', store=True)

    @api.depends('date_birthday')
    def _compute_birth_month(self):
        for rec in self:
            if rec.date_birthday:
                rec.birth_month = rec.date_birthday.month
            else:
                rec.birth_month = False

    @api.depends('name', 'employee_code')
    def _compute_fields_combination(self):
        for r in self:
            if r.name and r.employee_code:
                r.combination = r.name + ' (' + r.employee_code + ')'
            else:
                r.combination = r.name
    

class EmployeeRel(models.Model):
    _name = 'employee.rel'
    _description = 'Employee Rel'
    
    name = fields.Many2one('hr.employee', string="Tên nhân viên")
    emp_code = fields.Char(string="Mã nhân viên", compute="get_info_employee", store= True)
    job = fields.Many2one('hr.job', string="Chức vụ", compute="get_info_employee", store= True)
    department = fields.Many2one('hr.department', string="Phòng ban", compute="get_info_employee", store= True)
    amount_reward = fields.Float("Mức thưởng")
    amount_discipline = fields.Float("Số tiền")
    note = fields.Char(string="Ghi chú")
    
    person_reward = fields.Many2one('person.reward')
    person_discipline = fields.Many2one('person.discipline')
    
    @api.depends('name')
    def get_info_employee(self):
        for r in self:
            if r.name:
                r.emp_code = r.name.employee_code if r.name.employee_code else None
                r.department = r.name.department_id.id if r.name.department_id else None
                r.job = r.name.job_id.id if r.name.job_id else None


class DepartmentRel(models.Model):
    _name = 'department.rel'
    _description = 'Department Rel'
    
    company_code = fields.Many2one('hr.department', compute="get_info_department", store= True, string="Công ty")
    name_depart = fields.Many2one('hr.department', string="Tên phòng ban")
    
    unit_reward = fields.Many2one('unit.reward')
    unit_discipline = fields.Many2one('unit.discipline')
    
    @api.depends('name_depart')
    def get_info_department(self):
        for r in self:
            if r.name_depart:
                r.company_code = r.name_depart.company_id.id if r.name_depart.company_id else None


class WorkProcess(models.Model):
    _name = 'work.process'

    employee_id = fields.Many2one('hr.employee')

    start_date = fields.Date("Ngày bắt đầu")
    job_id = fields.Many2one('hr.job', "Chức vụ")
    number = fields.Char("Số quyết định")
    type = fields.Char("Loại quyết định")
    note = fields.Text("Ghi chú")



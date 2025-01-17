from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import re
import math


class SonHaEmployee(models.Model):
    _inherit = 'hr.employee'
    _rec_name = 'combination'
    _order = 'department_id, employee_code ASC'

    list_employee = fields.Many2many('hr.employee', 'ir_employee_group_rel',
                                     'employee_group_rel', 'employee_rel',
                                     string='List Staff', tracking=True)

    lower_grade = fields.Many2many('hr.employee', 'ir_lower_grade_id_rel',
                                   'lower_grade_id_rel', 'lower_grade_id',
                                    string="Lower Grade", tracking=True)

    kpi = fields.Many2many('hr.employee', 'ir_kpi_id_rel',
                           'kpi_id_rel', 'kpi_id',
                           string="Edit KPI", tracking=True)

    department_ids = fields.Many2many('hr.department', 'ir_department_ids_rel',
                                      'department_ids_rel', 'department_ids',
                                      string="Department", tracking=True)

    level = fields.Selection([
        ('N0', 'N0'),
        ('N1', 'N1'),
        ('N2', 'N2'),
        ('N3', 'N3'),
        ('N4', 'N4'),
        ('N5', 'N5'),
    ], string='Level', tracking=True)

    employee_approval = fields.Many2one('hr.employee', string="Người duyệt")

    date = fields.Date('Ngày', tracking=True)
    number = fields.Integer('Số', tracking=True)
    status_employee = fields.Selection([
        ('working', "Đang làm việc"),
        ('maternity_leave', "Nghỉ thai sản"),
        ('quit_job', 'Nghỉ việc'),
        ('trial', 'Thử việc')
    ], string='Trạng thái làm việc', tracking=True)

    date_quit = fields.Date("Ngày nghỉ việc", tracking=True)
    reason_quit = fields.Char("Lý do nghỉ việc", tracking=True)

    # các field page hr setting
    onboard = fields.Date('Ngày vào công ty', tracking=True)
    # type_contract = fields.Many2one('hr.contract', string="Loại hợp đồng")
    employee_code = fields.Char("Mã nhân viên", readonly=True, tracking=True)
    shift = fields.Many2one('config.shift', string="Ca làm việc", tracking=True, readonly=False)

    # các field page infomation page 1
    date_birthday = fields.Date("Ngày sinh", tracking=True)
    place_birthday = fields.Char("Nơi sinh", tracking=True)
    marital_status = fields.Selection([
        ('single', "Độc thân"),
        ('married', "Đã kết hôn"),
    ], string='Tình trạng hôn nhân', tracking=True)
    nation = fields.Char("Dân tộc")
    religion = fields.Selection([
        ('yes', "Có"),
        ('no', "Không"),
    ], string='Tôn giáo', tracking=True)
    hometown = fields.Char("Quê quán", tracking=True)
    permanent_address = fields.Char("Địa chỉ thường trú", tracking=True)
    current_residence = fields.Char("Nơi ở hiện tại", tracking=True)

    # các field page private infomation page 2
    number_cccd = fields.Char("Số CCCD", tracking=True)
    date_cccd = fields.Date("Ngày cấp", tracking=True)
    place_of_issue = fields.Char("Nơi cấp", tracking=True)
    passport_number = fields.Char("Số hộ chiếu", tracking=True)
    date_passport = fields.Date("Ngày hộ chiếu", tracking=True)
    expiration_date_passport = fields.Date("Ngày hết hạn", tracking=True)
    place_of_issue_passport = fields.Char("Nơi cấp hộ chiếu", tracking=True)
    number_visa = fields.Char("Số visa", tracking=True)
    date_visa = fields.Date("Ngày cấp(visa)", tracking=True)
    expiration_date_visa = fields.Date("Ngày hết hạn(visa)", tracking=True)
    place_of_issue_visa = fields.Char("Nơi cấp(visa)", tracking=True)
    reunion_day = fields.Date("Ngày vào Đoàn", tracking=True)
    place_reunion = fields.Char("Nơi vào(Đoàn)", tracking=True)
    fee_reunion = fields.Boolean("Đoàn phí", tracking=True)
    party_member_day = fields.Date("Ngày vào Đảng", tracking=True)
    place_party_member = fields.Char("Nơi vào Đảng", tracking=True)
    fee_party_member = fields.Boolean("Đảng phí", tracking=True)

    combination = fields.Char(string='Combination', compute='_compute_fields_combination', tracking=True, store=True)
    work_ids = fields.One2many('work.process', 'employee_id', string="Quá trình công tác")

    birth_month = fields.Integer(string="Sinh nhật", compute='_compute_birth_month', store=True, tracking=True)
    reception_date = fields.Date("Ngày tiếp nhận", tracking=True)
    culture_level = fields.Char("Trình độ văn hóa", tracking=True)
    tax_code = fields.Char("Mã số thuế", tracking=True)
    check_account = fields.Boolean('check_account', compute="check_account_user")

    total_compensatory = fields.Float("Thời gian nghỉ bù còn lại", compute="get_compensatory")

    compensatory = fields.Float("Nghỉ bù", default=0)

    @api.onchange('department_id')
    def get_shift_department(self):
        for r in self:
            if r.shift:
                break
            elif r.department_id and r.department_id.shift:
                r.shift = r.department_id.shift.id
            else:
                r.shift = None

    def get_compensatory(self):
        for r in self:
            r.total_compensatory = 0
            data = self.env['employee.attendance'].sudo().search([('employee_id', '=', r.id)])
            if data:
                over_time = data.mapped('over_time')
                data_compensatory = data.filtered(lambda x: x.compensatory > 0)
                leave_compensatory = 0
                if data_compensatory:
                    for rec in data_compensatory:
                        if rec.compensatory == 0.5:
                            so = ((math.ceil(rec.duration) * 60) - rec.shift.minutes_rest) / 60 if rec.duration else 0
                            leave_compensatory += so / 2
                        elif rec.compensatory == 1:
                            so = ((math.ceil(rec.duration) * 60) - rec.shift.minutes_rest) if rec.duration else 0
                            leave_compensatory += so / 60
                r.total_compensatory = r.compensatory + sum(over_time) - leave_compensatory

    @api.depends('user_id')
    def check_account_user(self):
        for r in self:
            if r.user_id:
                r.check_account = True
            else:
                r.check_account = False

    def create_user(self):
        for r in self:
            user_vals = {
                'name': r.name,
                'login': r.work_email if r.work_email != 'nan' and r.work_email else r.employee_code,
                'password': "123456",
                'email': r.work_email or '',
                'employee_ids': [(4, r.id)],
                'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
            }
            self.env['res.users'].sudo().create(user_vals)
            r.user_id = self.env['res.users'].sudo().search(['|', ('login', '=', r.employee_code),
                                                            ('login', '=', r.work_email)], limit=1)

    @api.depends('date_birthday', 'birthday')
    def _compute_birth_month(self):
        for rec in self:
            if rec.date_birthday:
                rec.birth_month = rec.date_birthday.month
            elif rec.birthday:
                rec.birth_month = rec.birthday.month
            else:
                rec.birth_month = False

    @api.depends('name', 'employee_code')
    def _compute_fields_combination(self):
        for r in self:
            if r.name and r.employee_code:
                r.combination = r.name + ' (' + r.employee_code + ')'
            else:
                r.combination = r.name

    def create(self, vals):
        val = {
            'name': vals['name']
        }
        self.env['res.partner'].sudo().create(val)
        resource_id = self.env['resource.resource'].sudo().create(val)
        vals['emergency_contact'] = vals['name']
        vals['resource_id'] = resource_id.id

        res = super(SonHaEmployee, self).create(vals)

        company_id = self.env['res.company'].sudo().search([('id', '=', res.company_id.id)])
        company_id.max_number += 1
        if not company_id.company_code:
            res.employee_code = '0' * company_id.zero_count + str(company_id.max_number)
        else:
            res.employee_code = company_id.company_code + '0' * company_id.zero_count + str(company_id.max_number)
        return res

    @api.onchange('status_employee')
    def onchange_status_employee(self):
        for s in self:
            if s.status_employee == 'quit_job':
                s.active = False
            else:
                s.active = True

    @api.constrains('employee_code')
    def check_employee_code(self):
        for record in self:
            conflicting_employee_code = self.search([
                ('employee_code', '=', record.employee_code),
                ('id', '!=', record.id),
            ], limit=1)

            if conflicting_employee_code:
                raise ValidationError(f"Đã tồn tại nhân viên có mã nhân viên là {record.employee_code}")

    @api.constrains('device_id_num')
    def check_device_id_num(self):
        for record in self:
            if record.device_id_num:
                conflicting_device_id_num = self.search([
                    ('device_id_num', '=', record.device_id_num),
                    ('id', '!=', record.id),
                ], limit=1)
                if conflicting_device_id_num:
                    raise ValidationError(f"Đã tồn tại mã chấm công là {record.device_id_num}")


class ResCompany(models.Model):
    _inherit = 'res.company'

    max_number = fields.Integer(string="Mã lớn nhất", compute="_compute_max_number",required=True)
    zero_count = fields.Integer(string="Số số 0", compute="_compute_max_number",required=True)
    company_code = fields.Char(string="Mã công ty")
    slip = fields.Integer("Đơn từ", default=0)
    shift = fields.Integer("Ca", default=0)

    def _compute_max_number(self):
        for r in self:
            employee_codes = self.env['hr.employee'].sudo().search([('company_id.id', '=', r.id)])
            max_number = 0
            max_str = ''
            for employee in employee_codes:
                if employee.employee_code:
                    match = re.search(r'(\d+)$', employee.employee_code)
                    if match:
                        number_str = match.group()
                        number = int(number_str)

                        if max_number < number:
                            max_number = number
                            max_str = number_str

            r.zero_count = len(max_str) - len(max_str.lstrip('0')) if max_str else 0
            r.max_number = max_number


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

    def create(self, vals):
        res = super(WorkProcess, self).create(vals)
        job_id = res.job_id.id
        res.employee_id.job_id = job_id
        return res


class Resources(models.Model):
    _inherit = 'resource.resource'

    name = fields.Char(required=False)




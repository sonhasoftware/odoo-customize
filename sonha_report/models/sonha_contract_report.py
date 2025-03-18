from odoo import api, fields, models

class SonhaContractReport(models.Model):
    _name = 'sonha.contract.report'

    name = fields.Char(string="Mã hợp đồng")
    employee_id = fields.Many2one('hr.employee', string="Nhân viên")
    employee_code = fields.Char("Mã nhân viên")
    date_start = fields.Date("Ngày bắt đầu hợp đồng")
    date_end = fields.Date("Ngày kết thúc")
    structure_type_id = fields.Many2one('hr.payroll.structure.type', string="Cấu trúc lương")
    department_id = fields.Many2one('hr.department', string="Bộ phận")
    job_id = fields.Many2one('hr.job', string="Chức vụ")
    contract_type_id = fields.Many2one('hr.contract.type', string="Kiểu hợp đồng")
    resource_calendar_id = fields.Many2one('resource.calendar', string="Thời gian làm việc")
    status = fields.Selection([('draft', "Mới"),
                               ('open', "Đang chạy"),
                               ('close', "Đã hết hạn"),
                               ('cancel', "Đã hủy")], string="Trạng thái")
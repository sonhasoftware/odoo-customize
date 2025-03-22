from odoo import api, fields, models

class MasterDataReport(models.Model):
    _name = 'master.data.report'


    employee_id = fields.Many2one('hr.employee', string="Nhân viên")
    department_id = fields.Many2one('hr.department', string="Phòng ban")
    attendance_time = fields.Datetime(string="Thời gian")
    month = fields.Integer(string="Tháng")

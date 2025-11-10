from odoo import models, fields, api


class LeaveLeft(models.Model):
    _name = 'leave.left'

    employee_id = fields.Many2one('hr.employee', string="Nhân viên")
    year = fields.Integer("Năm")
    start_date = fields.Date("Ngày mốc")
    th_1 = fields.Float("Phép còn tháng 1")
    th_2 = fields.Float("Phép còn tháng 2")
    th_3 = fields.Float("Phép còn tháng 3")
    th_4 = fields.Float("Phép còn tháng 4")
    th_5 = fields.Float("Phép còn tháng 5")
    th_6 = fields.Float("Phép còn tháng 6")
    th_7 = fields.Float("Phép còn tháng 7")
    th_8 = fields.Float("Phép còn tháng 8")
    th_9 = fields.Float("Phép còn tháng 9")
    th_10 = fields.Float("Phép còn tháng 10")
    th_11 = fields.Float("Phép còn tháng 11")
    th_12 = fields.Float("Phép còn tháng 12")
    leave_t1 = fields.Float("Phép sử dụng tháng 1")
    leave_t2 = fields.Float("Phép sử dụng tháng 2")
    leave_t3 = fields.Float("Phép sử dụng tháng 3")
    leave_t4 = fields.Float("Phép sử dụng tháng 4")
    leave_t5 = fields.Float("Phép sử dụng tháng 5")
    leave_t6 = fields.Float("Phép sử dụng tháng 6")
    leave_t7 = fields.Float("Phép sử dụng tháng 7")
    leave_t8 = fields.Float("Phép sử dụng tháng 8")
    leave_t9 = fields.Float("Phép sử dụng tháng 9")
    leave_t10 = fields.Float("Phép sử dụng tháng 10")
    leave_t11 = fields.Float("Phép sử dụng tháng 11")
    leave_t12 = fields.Float("Phép sử dụng tháng 12")

    def update_employee_leave_left(self):
        self.with_delay().cron_jon()

    def cron_jon(self):
        list_employee = self.env['hr.employee'].sudo().search([])
        for emp in list_employee:
            self.env['popup.synthetic.leave.report'].calculate_total_leave_left(emp)


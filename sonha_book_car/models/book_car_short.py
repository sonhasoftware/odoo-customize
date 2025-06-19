from odoo import models, fields, api


class BookCarShort(models.Model):
    _name = 'book.car.short'

    company_id = fields.Many2one('res.company', string="Công ty")
    department_id = fields.Many2one('hr.department', string="Phòng ban")
    employee_id = fields.Many2one('hr.employee', string="Người tạo")
    start_date = fields.Date("Ngày bắt đầu")
    book_end_date = fields.Date("Ngày kết thúc")
    start_time = fields.Float("Thời gian bắt đầu")
    end_time = fields.Float("Thời gian kết thúc")
    book_car = fields.Many2one('book.car')


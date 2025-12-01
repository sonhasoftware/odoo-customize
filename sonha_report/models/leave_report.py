from odoo import api, fields, models

class LeaveReport(models.Model):
    _name = 'leave.report'

    ns_id = fields.Many2one('hr.employee', string="Nhân viên", store=True)
    ma_ns = fields.Char(string="Mã nhân sự", store=True)
    ten_ns = fields.Char(string="Tên nhân sự", store=True)

    #==== Phép tổng hợp =====

    ton_dau = fields.Float(string="Tồn đầu", store=True)
    nhap = fields.Float(string="Nhập", store=True)
    xuat = fields.Float(string="Xuất", store=True)
    ton_cuoi = fields.Float(string="Tồn cuối", store=True)

    #==== Phép chi tiết =====

    ngay = fields.Date(string="Ngày", store=True)
    chung_tu = fields.Selection([('DK', "Đầu kỳ"),
                                 ('TK', "Trong kỳ"),
                                 ('CK', "Cuối kỳ")], string="Chứng từ", store=True)
    phep_them = fields.Float(string="Phép thêm", store=True)
    phep_su_dung = fields.Float(string="Phép sử dụng", store=True)
    in_dam = fields.Integer(string="In đậm", store=True)


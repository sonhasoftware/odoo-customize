from odoo import models, fields, api


class SonhaWordReport(models.Model):
    _name = 'sonha.word.report'

    ns_id = fields.Many2one('hr.employee', string="Nhân sự", store=True)
    ma_ns = fields.Char(string="Mã nhân viên", store=True)
    ten_ns = fields.Char(string="Tên nhân viên", store=True)
    bo_phan_id = fields.Many2one('hr.department', string="Phòng ban", store=True)
    ten_bp = fields.Char(string="Tên phòng ban", store=True)
    ngay = fields.Date(string="Ngày", store=True)
    key_form = fields.Integer(string="Key form", store=True)

    # ===== Báo cáo ca =======
    ca_id = fields.Many2one('config.shift', string="Ca", store=True)
    ten_ca = fields.Char(string="Tên ca", store=True)
    loai_don = fields.Selection([('dang_ky_ca', "Đăng ký ca"),
                                 ('doi_ca', "Đổi ca")], string="Loại đơn", store=True)

    # ===== Báo cáo làm thêm =====
    gio_bd = fields.Float(string="Giờ bắt đầu", store=True)
    gio_kt = fields.Float(string="Giờ kết thúc", store=True)
    so_gio_lt = fields.Float(string="Số giờ làm thêm", store=True)
    tt_don = fields.Selection([('draft', "Nháp"),
                               ('waiting', "Chờ duyệt"),
                               ('confirm', "Chờ duyệt"),
                               ('done', "Đã duyệt"),
                               ('cancel', "Hủy")], string="Trạng thái", store=True)


    # ===== Báo cáo đơn từ ======

from odoo import api, fields, models


class NhanVien(models.Model):
    _name = 'nhan.vien'

    ma_nhan_vien = fields.Char(string="Mã nhân viên")
    ten_nhan_vien = fields.Text(string="Tên nhân viên")
    chi_nhanh_id = fields.Many2one('bh.branch', string="Chi nhánh")
    dia_chi = fields.Text(string="Địa chỉ")
    dien_thoai = fields.Text(string="Điện thoại")
    lock = fields.Boolean(string="Lock")
    dien_thoai2 = fields.Text(string="Điện thoại 2")
    # thong_tin_bao_hanh_ids = fields.One2many('thong.tin.bao.hanh', 'nhan_vien_id', string="Thông tin bảo hành")
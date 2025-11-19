from odoo import api, fields, models, _


class BaoCaoTongHop(models.Model):
    _name = 'bao.cao.tong.hop'

    ngay_ct = fields.Date("Ngày")
    chung_tu = fields.Char("Chứng từ")
    ngay_ht = fields.Date("Ngày dự kiến HT")
    ten_nguoi_tao = fields.Char("Người tạo")
    ket_thuc = fields.Integer("ket thúc")
    mau = fields.Integer("Màu")
    tt_don = fields.Char("Trạng thái")

from odoo import api, fields, models, _


class BaoCaoVanBan(models.Model):
    _name = 'bao.cao.van.ban'

    ngay_ct = fields.Date("Ngày")
    chung_tu = fields.Char("Chứng từ")
    ngay_ht = fields.Date()

    nguoi_tao = fields.Integer()
    ten_nguoi_tao = fields.Char()

    user_duyet = fields.Integer()
    ten_nguoi_duyet = fields.Char("Người duyệt")

    is_approved = fields.Boolean()

    xu_ly = fields.Integer()
    stt_xu_ly = fields.Integer()
    ten_xu_ly = fields.Char("Bước xử lý")

    dl_vb_h = fields.Integer()
    ngay_bd_duyet = fields.Datetime("Thời gian tính duyệt")

    ngay_duyet = fields.Datetime("Thời gian duyệt")
    sn_duyet = fields.Float("Số ngày phải duyệt")
    ngay_yc_ht = fields.Datetime()
    ngay_duyet00 = fields.Datetime()

    tt_don = fields.Text("Trạng thái")
    mau = fields.Integer()

from odoo import models, fields


class DKVanBanTH(models.Model):
    _name = 'dk.vb.th'

    ngay_ct = fields.Date(string="Ngày làm đơn", store=True)
    chung_tu = fields.Char(string="Số đơn", store=True)
    ngay_ht = fields.Date(string="Ngày hoàn thành", store=True)
    dvcs = fields.Many2one('res.company', "Đơn vị", store=True)

    id_loai_vb = fields.Many2one('dk.loai.vb', string="Loại VB", store=True)

    noi_dung = fields.Html("Nội dung chi tiết hồ sơ các đơn vị đăng ký", store=True)

    tn_pb = fields.Boolean(string="Tổng ngày PB", store=True)
    sn_pb = fields.Float(string="Số ngày PB", store=True)

    tn_bdh = fields.Boolean(string="Tổng ngày BDH", store=True)
    sn_bdh = fields.Float(string="Số ngày BDH", store=True)

    tn_ct = fields.Boolean(string="Tổng ngày CT/PCT", store=True)
    sn_ct = fields.Float(string="Số ngày CT/PCT", store=True)

    user_duyet = fields.Many2one('res.users', string="Người duyệt", store=True)

    xu_ly = fields.Many2one('dk.xu.ly', string="Tiến trình xử lý", store=True)

    sn_duyet = fields.Float(string="Số ngày duyệt", store=True)
    sn_pb_duyet = fields.Float(string="Số ngày PB duyệt", store=True)

    # Thời gian duyệt (datetime)
    ngay_bd_duyet = fields.Datetime(string="Ngày bắt đầu duyệt", store=True)
    ngay_duyet = fields.Datetime(string="Ngày duyệt", store=True)

    dk_vb_h = fields.Many2one('dk.vb.h', store=True)
    dk_vb_d = fields.Many2one('dk.vb.d', store=True)

from odoo import api, fields, models


class KetQuaKhachHang(models.Model):
    _name = 'ket.qua.khach.hang'

    ma_khach = fields.Char("Mã")
    ten_khach = fields.Char("Tên")
    key_kh = fields.Many2one('mdm.khach.hang')
    score_ten = fields.Float("% Tên giống nhau")
    score_mst = fields.Float("% MST giống nhau")
    score_dia_chi = fields.Float("% Địa chỉ giống nhau")
    score_sdt = fields.Float("% SĐT giống nhau")
    score_cccd = fields.Float("% CCCD giống nhau")
    record = fields.Many2one('mdm.khach.hang')

    dia_chi_khach = fields.Char(related='record.dia_chi_khach', string="Địa chỉ khách",)
    ma_cn = fields.Char(related='record.ma_cn.ma', string="Mã Chi nhánh")
    nhom_khach = fields.Char(related='record.nhom_khach.ma', string="Nhóm khách")
    ten_salesman = fields.Text(related='record.ten_salesman.ten', string="Tên Salesman")
    ma_dms = fields.Char(related='record.ma_dms', string="Mã DMS")
    ma_tinh = fields.Text(related='record.ma_tinh.ten', string="Mã tỉnh")
    kinh_do = fields.Char(related='record.kinh_do', string="Kinh độ")
    vi_do = fields.Char(related='record.vi_do', string="Vĩ độ")
    so_dien_thoai = fields.Char(related='record.so_dien_thoai', string="Số điện thoại")
    dat_nuoc = fields.Text(related='record.dat_nuoc.ten', string="Đất nước")
    khu_vuc = fields.Text(related='record.khu_vuc.ten', string="Khu vực")
    vung = fields.Char(related='record.vung', string="Vùng")
    qlv = fields.Text(related='record.qlv.ten', string="QLV")
    mst = fields.Char(related='record.mst', string="MST")
    cccd = fields.Char(related='record.cccd', string="CCCD")

    sort_score = fields.Float(compute="_compute_sort_score", store=True)

    @api.depends('score_mst', 'score_sdt', 'score_ten', 'score_cccd')
    def _compute_sort_score(self):
        for rec in self:
            if rec.score_mst:
                rec.sort_score = rec.score_mst + 300
            elif rec.score_cccd:
                rec.sort_score = rec.score_cccd + 200
            elif rec.score_sdt:
                rec.sort_score = rec.score_sdt + 200
            else:
                rec.sort_score = rec.score_ten + 100


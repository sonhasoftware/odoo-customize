from odoo import api, fields, models


class KetQuaTongHop(models.Model):
    _name = 'ket.qua.tong.hop'
    _rec_name = 'ma'

    ma = fields.Char("Mã")
    ten = fields.Text("Tên")
    mdm = fields.Many2one('mdm.tong.hop')
    score = fields.Float("% Giống nhau")
    record = fields.Many2one('mdm.tong.hop')
    score_group = fields.Float("% Giống nhau group")

    chung_loai1 = fields.Text(related='record.chung_loai1.ten', string="Chủng loại 1")
    chung_loai2 = fields.Text(related='record.chung_loai2.ten', string="Chủng loại 2")
    linh_vuc = fields.Text(related='record.linh_vuc.ten', string="Lĩnh vực")
    nganh_hang = fields.Text(related='record.nganh_hang.ten', string="Ngành hàng")
    nhan_hang = fields.Text(related='record.nhan_hang.ten', string="Nhãn hàng")
    chat_lieu = fields.Text(related='record.chat_lieu.ten', string="Chất liệu")
    do_bong = fields.Text(related='record.do_bong.ten', string="Độ bóng")
    do_day = fields.Text(related='record.do_day.ten', string="Độ dày")
    dung_tich = fields.Text(related='record.dung_tich.ten', string="Dung tích")


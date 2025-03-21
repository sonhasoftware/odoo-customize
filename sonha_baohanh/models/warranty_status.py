from odoo import api, fields, models


class WarrantyStatus(models.Model):
    _name = 'warranty.status'
    _rec_name ='warranty_status_name'

    warranty_status_code = fields.Char(string="Mã trạng thái")
    warranty_status_name = fields.Text(string="Tên trạng thái")
    #thong_tin_bao_hanh_ids = fields.One2many('thong.tin.bao.hanh', 'trang_thai_id', string="Thông tin bảo hành")
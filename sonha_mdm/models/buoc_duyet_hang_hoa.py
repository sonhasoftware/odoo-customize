from odoo import fields, models, api


class BuocDuyetHangHoa(models.Model):
    _name = 'buoc.duyet.hang.hoa'
    _description = 'Bước duyệt hàng hóa'

    sequence = fields.Integer(default=1, string="STT")
    phuong_thuc = fields.Selection([('ql', 'Quản lý trực tiếp'),
                                    ('vt', 'Vai trò')],
                                   default='ql', required=True, string="Phương thức")
    vai_tro = fields.Many2one('vai.tro', string="Tên vai trò")
    ten_nguoi_duyet = fields.Many2one('res.users')
    da_duyet = fields.Boolean("Đã duyệt")

    key = fields.Many2one('mdm.tong.hop')

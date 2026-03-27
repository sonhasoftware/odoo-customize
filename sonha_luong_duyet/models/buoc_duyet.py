from odoo import fields, models, api


class BuocDuyet(models.Model):
    _name = 'buoc.duyet'
    _description = 'Bước duyệt'

    sequence = fields.Integer(default=1, string="STT")
    phuong_thuc = fields.Selection([('ql', 'Quản lý trực tiếp'),
                                    ('vt', 'Vai trò')],
                                   default='ql', required=True, string="Phương thức")
    vai_tro = fields.Many2one('vai.tro', string="Tên vai trò")
    ten_nguoi_duyet = fields.Many2many('res.users', string="Tên người duyệt")

    luong_duyet = fields.Many2one('luong.duyet')

    @api.onchange('vai_tro')
    def _onchange_vai_tro(self):
        for rec in self:
            if rec.vai_tro:
                rec.ten_nguoi_duyet = [(6, 0, rec.vai_tro.ten_nguoi_duyet.ids)]
            else:
                rec.ten_nguoi_duyet = [(5, 0, 0)]

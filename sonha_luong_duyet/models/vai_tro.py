from odoo import fields, models, api


class VaiTro(models.Model):
    _name = 'vai.tro'
    _description = 'Vai trò'
    _rec_name = 'ten'

    ten = fields.Char(required=True, string="Tên vai trò")
    ten_nguoi_duyet = fields.Many2many('res.users', string="Tên người duyệt", required=True)


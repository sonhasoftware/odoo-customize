from odoo import fields, models, api


class LuongDuyet(models.Model):
    _name = 'luong.duyet'
    _description = 'Luồng duyệt'
    _rec_name = 'ten'

    ten = fields.Char(required=True, string="Tên")
    dvcs = fields.Many2one('res.company', required=True, string="Công ty")

    model_id = fields.Many2one('ir.model', string="Áp dụng cho Model", ondelete='cascade', required=True,)

    step_ids = fields.One2many(
        'buoc.duyet',
        'luong_duyet',
        string='Các bước duyệt'
    )

from odoo import api, fields, models


class MDMChatLieu(models.Model):
    _name = 'mdm.chat.lieu'
    _rec_name = 'ten'

    ma = fields.Char("Mã", store=True)
    ten = fields.Text("Tên", store=True)

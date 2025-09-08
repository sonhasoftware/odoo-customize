from odoo import models, fields, api


class SonHaPlant(models.Model):
    _name = 'sonha.plant'
    _rec_name = 'x_full_name'

    plant = fields.Char("Plant")
    name = fields.Char("Tên kho")
    company_id = fields.Many2one('res.company', string="Công ty")
    x_country_id = fields.Many2one('res.country', string='Quốc gia')
    x_state_id = fields.Many2one('res.country.state', string='Tỉnh thành', domain="[('country_id', '=', x_country_id)]")
    x_street = fields.Char('Địa chỉ đầy đủ')
    x_full_name = fields.Char("Tên đầy đủ", compute="get_full_name", store=True)

    @api.depends('plant', 'name')
    def get_full_name(self):
        for r in self:
            if r.name and r.plant:
                r.x_full_name = f"{r.plant} - {r.name}"
            else:
                r.x_full_name = ""
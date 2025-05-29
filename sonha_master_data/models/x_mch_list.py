from odoo import fields, models, api


class XMchList(models.Model):
    _name = 'x.mch.list'
    _rec_name = 'x_full_name'

    name = fields.Char("Tên MCH")
    x_mch_code = fields.Char("Mã MCH")
    x_parent_id = fields.Many2one('x.mch.list', string="MCH cha")
    child_ids = fields.One2many('x.mch.list', 'x_parent_id', string="MCH con")
    level = fields.Integer("Cấp MCH")
    x_full_name = fields.Char("Tên đầy đủ", compute="get_full_name", store=True)

    @api.depends('name', 'x_mch_code')
    def get_full_name(self):
        for r in self:
            if r.name and r.x_mch_code:
                r.x_full_name = f"[{r.x_mch_code}] {r.name}"
            else:
                r.x_full_name = ""


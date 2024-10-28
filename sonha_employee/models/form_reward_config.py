from odoo import models, fields

class FormReward(models.Model):
    _name = 'form.reward.config'
    _description = 'Form Reward Config'
    
    #
    id = fields.Char(string="ID hình thức", required = True)
    name = fields.Char(string="Tên hình thức khen thưởng")
    type = fields.Selection([('reward', 'Khen thưởng'), ('discipline', 'Kỉ luật')], string="Loại khen thưởng")
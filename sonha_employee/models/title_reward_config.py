from odoo import models,fields

class TitleReward(models.Model):
    _name = 'title.reward.config'
    _description = 'Title Reward Config'
    
    #
    id = fields.Char(string="ID Hình thức", required = True)
    name  = fields.Char(string="Tên hình thức khen thưởng")
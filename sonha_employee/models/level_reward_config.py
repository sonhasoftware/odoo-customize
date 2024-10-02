from odoo import models, fields

class LevelReward(models.Model):
    _name = 'level.reward.config'
    _description = 'Level Reward Config'
    
    id = fields.Char(string="ID Cấp", required= True)
    name = fields.Char(string="Tên Cấp khen thưởng")
    
    
    
    
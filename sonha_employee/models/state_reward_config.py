from odoo import models, fields

class StateReward(models.Model):
    _name = 'state.reward.config'
    _description = 'State Reward Config'
    
    id = fields.Char(string="ID Trạng thái", required = True)
    name  = fields.Char(string="Tên trạng thái")
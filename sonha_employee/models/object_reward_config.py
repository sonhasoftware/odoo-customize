from odoo import models, fields

class ObjectReward(models.Model):
    _name = 'object.reward.config'
    _description = 'Object Reward Config'
    
    #
    id = fields.Char(string="ID đối tượng", required = True)
    name = fields.Char(string="Tên đối tượng khen thưởng")
    type = fields.Selection([('unit', 'Đơn vị'), ('person', 'Cá nhân')], string="Loại đối tượng")
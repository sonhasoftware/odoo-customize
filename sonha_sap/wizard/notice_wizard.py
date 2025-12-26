from odoo import fields, models, api


class NoticeWizard(models.TransientModel):
    _name = 'notice.wizard'

    notice = fields.Char(string="Nội dung")
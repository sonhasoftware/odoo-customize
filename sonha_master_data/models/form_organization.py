from odoo import models, fields, api


class FormOrganization(models.Model):
    _name = 'form.organization'
    _rec_name = 'form_of_org'

    form_of_org = fields.Char("Hình thức chủ sở hữu doanh nghiệp")
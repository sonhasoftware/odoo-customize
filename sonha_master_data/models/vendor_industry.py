from odoo import models, fields, api


class VendorIndustry(models.Model):
    _name = 'vendor.industry'
    _rec_name = 'vendor_type'

    vendor_type = fields.Char("Loại NCC(SX/TM)")
from odoo import api, fields, models
import requests


class DataSap(models.Model):
    _name = 'data.sap'

    url = fields.Char(string="URL API")
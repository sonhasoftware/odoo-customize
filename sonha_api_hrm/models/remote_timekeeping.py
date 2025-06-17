from odoo import api, fields, models


class RemoteTimekeeping(models.Model):
    _name = 'remote.timekeeping'

    name = fields.Char("Name")
    bssid = fields.Char("bssid")
    latitude = fields.Float("latitude")
    longitude = fields.Float("longitude")
    radius = fields.Float("radiusInMeters")



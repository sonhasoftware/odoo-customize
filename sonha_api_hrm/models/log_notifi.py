from odoo import api, fields, models


class LogNotifi(models.Model):
    _name = 'log.notifi'

    token = fields.Char(string="Token")
    title = fields.Char(string="Title")
    body = fields.Text(string="Body")
    data = fields.Text(string="Data")
    type = fields.Integer(string="Type")
    taget_screen = fields.Char(string="Target Screen")
    message_id = fields.Char(string="Message ID")
    badge = fields.Integer(string="Badge")
    datetime = fields.Datetime(string="Datetime")
    userid = fields.Char(string="User ID")
    is_read = fields.Boolean(default=False)

    # Không bắt buộc
    employeeid = fields.Char(string="Employee ID")
    id_application = fields.Char(string="Application ID")

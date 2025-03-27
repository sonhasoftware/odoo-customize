from odoo import api, fields, models

class BhBranch(models.Model):
    _name = 'bh.branch'
    _rec_name = 'branch_name'

    branch_name = fields.Text(string="Tên chi nhánh")
    address = fields.Text(string="Địa chỉ")
    plant = fields.Char(string="Plant")
    warehouse_tsc = fields.Char(string="Mã kho TSC")
    warehouse_tp = fields.Char(string="Mã kho TP")
    warehouse_tk = fields.Char(string="Mã kho chờ TK")
    branch_code = fields.Char(string="Mã chi nhánh")
    province_id = fields.Many2one('province', string="Tỉnh thành")
    district_id = fields.Many2one('district', string="Quận/huyện", domain="[('province_id', '=', province_id)]")
    # ward_commune_id = fields.Many2one('ward.commune', string="Phường/xã", domain="[('district_id', '=', district_id)]")
    company_id = fields.Many2one("res.company", string="Công ty")
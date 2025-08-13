from odoo import models, fields, api


class VendorPurchase(models.Model):
    _name = 'vendor.purchase'

    purchasing_org = fields.Many2one('sale.organization', string="Tổ chức mua hàng")
    incoterm = fields.Many2one('cus.incoterm', string="Incoterm")
    auto_po = fields.Boolean("Tự động tạo PO", default=True)
    indicator = fields.Boolean("Đối chiếu HĐ sau khi nhận")
    purchasing_group = fields.Many2one('purchasing.group', string="Nhóm mua hàng")
    plan_del_time = fields.Char("Ngày giao dự kiến")
    order_currency = fields.Many2one('order.currency', string="Loại tiền mua")
    minimum_order = fields.Float("Giá trị tối thiểu")
    representative = fields.Char("Người đại diện")
    group_supplier = fields.Char("Tiêu chí xác định bảng giá")
    price_date_control = fields.Date("Kiểm soát ngày xác định giá")
    declare_vendor = fields.Many2one('declare.md.supplier')
    md_vendor = fields.Many2one('md.supplier')


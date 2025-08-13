from odoo import models, fields, api


class CustomerSale(models.Model):
    _name = 'customer.sale'

    declare_md_customer = fields.Many2one('declare.md.customer')
    sale_organization = fields.Many2one('sale.organization', string="Tổ chức bán hàng", required=True)
    distribution_channel = fields.Many2one('distribution.channel', string="Kênh bán hàng", required=True)
    division = fields.Many2one('x.division', string="Lĩnh vực", required=True)
    currency = fields.Selection([('vnd', "VND - Đồng Việt Nam"),
                                 ('usd', "USD - Đô la Mỹ"),
                                 ('eur', "EUR - Đồng Euro"),
                                 ('cny', "CNY - Nhân dân tệ"),
                                 ('mmk', "MMK - Đồng Kyat")], string="Tiền tệ", required=True)
    relevant_settlement = fields.Boolean("Chiết khấu tích lũy", default=True)
    order_combination = fields.Boolean("Gộp đơn khi giao")
    pod_relevant = fields.Boolean("Xuất kho 2 bước", default=True)
    incoterm_more = fields.Char("Bổ sung Incoterms")
    tax_classification = fields.Selection([('no', "0 - Không chịu thuế"),
                                           ('yes', "1 - Chịu thuế")],
                                          string="Điều kiện chịu thuế", required=True)
    sale_district = fields.Many2one('sale.district', string="Vùng kinh doanh")
    incoterm = fields.Many2one('cus.incoterm', string="Incoterms")
    cus_group = fields.Many2one('cus.group', string="Nhóm khách hàng (sale)")
    cus_group_1 = fields.Many2one('cus.group.1', string="Nhóm khách hàng 1")
    customer_price_group = fields.Many2one('customer.price.group', string="Nhóm khách theo giá")
    shipping_condition = fields.Many2one('shipping.condition', string="Điều kiện vận chuyển")
    customer_assignment_group = fields.Many2one('customer.assignment.group', string="Mã hạch toán doanh thu",
                                                required=True)
    sale_office = fields.Many2one('sale.office', string="Chi nhánh")
    plant = fields.Many2one('stock.warehouse', string="Plant")
    payment_term = fields.Many2one('payment.term', string="Thời hạn thanh toán", required=True)
    md_customer = fields.Many2one('md.customer')

    sold_to = fields.Many2one('declare.md.customer', "Bên mua hàng", domain="[('status', '=', 'done')]")
    ship_to = fields.Many2one('declare.md.customer', "Bên nhận hàng", domain="[('status', '=', 'done')]")
    bill_to = fields.Many2one('declare.md.customer', "Bên nhận hóa đơn", domain="[('status', '=', 'done')]")
    payer = fields.Many2one('declare.md.customer', "Bên thanh toán", domain="[('status', '=', 'done')]")
    contract_person = fields.Char("Người liên lạc của khách")
    sale_employee = fields.Many2one('declare.md.saleman', "Nhân viên bán hàng")
    company_code = fields.Many2one('company.code', "Mã công ty")
    credit_ctrl_area = fields.Char("Vùng quản lý tín dụng")




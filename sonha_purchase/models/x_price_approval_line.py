from odoo import models, fields,_

# các trường comment là các trường cần thiết, có thể chưa có liên kết với model khác
class XPriceApprovalLine(models.Model):
    _name = 'x.price.approval.line'

    # x_pp_id = fields.Many2one('x.price.approval',string="Duyệt giá")
    # x_reference_price_id = fields.Many2one('x.reference.price',string="Kho nhận hàng - Tên sản phẩm")
    # x_company_id = fields.Many2one('res.company',string="Đơn vị đặt")
    # x_product_id = fields.Many2one('product.product',string="Sản phẩm")
    # x_product_uom_id = fields.Many2one('uom.uom.custom',string="Đơn vị tính")
    # x_supplier_selected_id = fields.Many2one('res.partner',string="NCC được chọn")
    x_ord_qty = fields.Float(string="Số lượng yêu cầu")
    # x_currency_id = fields.Many2one('res.currence',string="Tiền tệ")
    # x_supplier_price = fields.Monetary(string="Đơn giá", currency_field='x_currency_id')
    x_total = fields.Float(string="Tổng")
    # x_currency2_id = fields.Many2one('res.currency',string="X Currency2")

    def sync_x_price_approval_line_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = "SELECT x_ord_qty,x_total FROM x_price_approval_line"

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            for r in data:
                records_to_create.append({
                    'x_ord_qty': r.get('x_ord_qty'),
                    'x_total': r.get('x_total')
                })

        if records_to_create:
            self.sudo().create(records_to_create)
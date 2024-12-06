from odoo import models, fields,_

# các trường comment là các trường cần thiết, có thể chưa có liên kết với model khác
class XPriceApprovalLine(models.Model):
    _name = 'x.price.approval.line'

    x_pp_id = fields.Many2one('x.price.approval',string="Duyệt giá")
    # x_reference_price_id = fields.Many2one('x.reference.price',string="Kho nhận hàng - Tên sản phẩm")
    # x_company_id = fields.Many2one('res.company',string="Đơn vị đặt")
    # x_product_id = fields.Many2one('product.product',string="Sản phẩm")
    # x_product_uom_id = fields.Many2one('uom.uom.custom',string="Đơn vị tính")
    # x_supplier_selected_id = fields.Many2one('res.partner',string="NCC được chọn")
    x_ord_qty = fields.Float(string="Số lượng yêu cầu")
    # x_currency_id = fields.Many2one('res.currency',string="Tiền tệ")
    # x_supplier_price = fields.Monetary(string="Đơn giá")
    x_total = fields.Float(string="Tổng")
    # x_currency2_id = fields.Many2one(comodel_name='res.currency', default=lambda self: self.env.ref('base.VND'))

    def sync_x_price_approval_line_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = """
            SELECT 
                id,
                x_pp_id,
                x_reference_price_id,
                x_company_id,
                x_product_id,
                x_product_uom_id,
                x_supplier_selected_id,
                x_ord_qty,
                x_currency_id,
                x_supplier_price,
                x_total,
                x_currency2_id
            FROM 
                x_price_approval_line
        """

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            self.with_context(active_test=False).sudo().search([]).unlink()
            for r in data:
                records_to_create.append({
                    'x_pp_id': r.get('x_pp_id'),
                    # 'x_reference_price_id': r.get('x_reference_price_id'),
                    # 'x_company_id': r.get('x_company_id'),
                    # 'x_product_id': r.get('x_product_id'),
                    # 'x_product_uom_id': r.get('x_product_uom_id'),
                    # 'x_supplier_selected_id': r.get('x_supplier_selected_id'),
                    'x_ord_qty': r.get('x_ord_qty'),
                    # 'x_currency_id': r.get('x_currency_id'),
                    # 'x_supplier_price': r.get('x_supplier_price'),
                    'x_total': r.get('x_total'),
                    # 'x_currency2_id' : r.get('x_currency2_id'),
                })

        if records_to_create:
            created_records = self.sudo().create(records_to_create)

            for record, r in zip(created_records, data):
                self.env.cr.execute("""
                            UPDATE {} 
                            SET id = %s 
                            WHERE id = %s
                        """.format(self._table), (r.get('id'), record.id))
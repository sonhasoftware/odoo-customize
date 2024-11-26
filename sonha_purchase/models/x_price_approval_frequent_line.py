from odoo import models, fields, _


# các tường comment là cần thiết nhưng có thể chưa có model liên kết
class XPriceApprovalFrequentLine(models.Model):
    _name = "x.price.approval.frequent.line"

    # x_pp_frequent_id = fields.Many2one('x.price.approval.frequent',string="Duyệt giá")
    # x_product_id = fields.Many2one('product.product',string="Sản phẩm")
    # x_product_uom_id = fields.Many2one('uom.uom.custom',string="Đơn vị tính")
    x_ord_qty = fields.Float(string="Số lượng tối thiểu")
    x_supplier_price = fields.Float(string="Giá được chọn")
    # x_supplier_selected_id = fields.Many2one('res.partner',string="NCC được chọn")
    # company_id = fields.Many2one('res.company',string="Công ty")
    x_start_date = fields.Date(string="Ngày hiệu lực giá")
    x_end_date = fields.Date(string="Ngày hết hiệu lực")
    x_note = fields.Char(string="Ghi chú")
    x_price_chosen = fields.Boolean(string="Giá được chọn")
    # x_warehouse_id = fields.Many2one('stock.warehouse',string="Kho pháp nhân mua")
    x_lock_edit = fields.Boolean(string="Đã khóa")
    synch_sap = fields.Boolean(string="Đã đồng bộ SAP")
    # x_pp_frequent_state = fields.Selection(
    #     selection=[
    #         # không thấy option trong odoo15
    #     ],
    #     string="Trạng thái"
    # )
    x_manual_price = fields.Boolean(string="Giá mua gia công")
    x_need_qty = fields.Float(string="Số lượng yêu cầu")
    x_price_per_unit = fields.Float(string="Giá trên 1 đơn vị")
    # x_supplier_selected_id1 = fields.Many2one('res.partner',string="NCC1")
    x_supplier_price1 = fields.Float(string="Giá NCC1")
    # x_supplier_selected_id2 = fields.Many2one('res.partner',string="NCC2")
    x_supplier_price2 = fields.Float(string="Giá NCC2")
    # x_supplier_selected_id3 = fields.Many2one('res.partner',string="NCC3")
    x_supplier_price3 = fields.Float(string="Giá NCC3")
    # x_po_id = fields.Many2one('purchase.order',string="X Po")
    # x_last_price = fields.Monetary(string="Giá đặt lần cuối")
    state = fields.Selection(
        selection=[
            ('draft', 'Nháp'),
            ('to_approve', 'Chờ duyệt'),
            ('wait_for_add', 'Chờ bổ sung'),
            ('approved', "Đã duyệt"),
            ('cancel', 'Từ chối'),
        ],
        string="Trạng thái"
    )
    # x_user_edit = fields.Many2one('res.users',string="Người bổ sung thông tin phiếu")
    x_frequent_prd = fields.Boolean(string="Cần PCT duyệt")
    # x_true_price_unit = fields.Monetary(string="Đơn giá tròn trên X đơn vị")
    x_per = fields.Integer(string="X đơn vị")

    def sync_x_price_approval_frequent_line_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = """
            SELECT 
                x_pp_frequent_id,
                x_product_id,
                x_product_uom_id,
                x_ord_qty,
                x_supplier_price,
                x_supplier_selected_id,
                company_id,
                x_start_date,
                x_end_date,
                x_note,
                x_price_chosen,
                x_warehouse_id,
                x_lock_edit,
                synch_sap,
                x_pp_frequent_state,
                x_manual_price,
                x_need_qty,
                x_price_per_unit,
                x_supplier_selected_id1,
                x_supplier_price1,
                x_supplier_selected_id2,
                x_supplier_price2,
                x_supplier_selected_id3,
                x_supplier_price3,
                x_po_id,
                x_last_price,
                state,
                x_user_edit,
                x_frequent_prd,
                x_true_price_unit,
                x_per
            FROM 
                x_price_approval_frequent_line
        """

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            for r in data:
                records_to_create.append({
                    # 'x_pp_frequent_id': r.get('x_pp_frequent_id'),
                    # 'x_product_id': r.get('x_product_id'),
                    # 'x_product_uom_id': r.get('x_product_uom_id'),
                    'x_ord_qty': r.get('x_ord_qty'),
                    'x_supplier_price': r.get('x_supplier_price'),
                    # 'x_supplier_selected_id': r.get('x_supplier_selected_id'),
                    # 'company_id': r.get('company_id'),
                    'x_start_date': r.get('x_start_date'),
                    'x_end_date': r.get('x_end_date'),
                    'x_note': r.get('x_note'),
                    'x_price_chosen': r.get('x_price_chosen'),
                    # 'x_warehouse_id': r.get('x_warehouse_id'),
                    'x_lock_edit': r.get('x_lock_edit'),
                    'synch_sap': r.get('synch_sap'),
                    # 'x_pp_frequent_state': r.get('x_pp_frequent_state'),
                    'x_manual_price': r.get('x_manual_price'),
                    'x_need_qty': r.get('x_need_qty'),
                    'x_price_per_unit': r.get('x_price_per_unit'),
                    # 'x_supplier_selected_id1': r.get('x_supplier_selected_id1'),
                    'x_supplier_price1': r.get('x_supplier_price1'),
                    # 'x_supplier_selected_id2': r.get('x_supplier_selected_id2'),
                    'x_supplier_price2': r.get('x_supplier_price2'),
                    # 'x_supplier_selected_id3': r.get('x_supplier_selected_id3'),
                    'x_supplier_price3': r.get('x_supplier_price3'),
                    # 'x_po_id': r.get('x_po_id'),
                    # 'x_last_price': r.get('x_last_price'),
                    'state': r.get('state'),
                    # 'x_user_edit': r.get('x_user_edit'),
                    'x_frequent_prd': r.get('x_frequent_prd'),
                    # 'x_true_price_unit': r.get('x_true_price_unit'),
                    'x_per': r.get('x_per')
                })

        if records_to_create:
            self.sudo().create(records_to_create)

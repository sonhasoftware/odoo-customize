from odoo import models,fields,_

class XSupplierContract(models.Model):
    _name = 'x.supplier.contract'

    name = fields.Char(string="Số hợp đồng")
    # x_supplier_id = fields.Many2one('res.partner.custom',string="Nhà cung cấp")
    x_date_from = fields.Date(string="Ngày hiệu lực")
    x_date_to = fields.Date(string="Tới ngày")
    x_delivery_time_estimate = fields.Integer(string="Thời gian giao hàng ước tính (ngày)")
    state = fields.Selection(
        selection=[
            ('draft','Nháp'),
            ('open','Đang hiệu lưc'),
            ('close','Hết hạn')
        ],
        string="Trạng thái"
    )
    x_contract_type = fields.Selection(
        selection=[
            ('contract_tmp','Hợp đồng khung'),
            ('contract_po','Hợp đồng đơn'),
        ],
        string="Loại hợp đồng"
    )
    # x_po_id = fields.Many2one('purchase.order',string="Đơn mua hàng")
    price_validity_conditions = fields.Text(string="Điều kiện hiệu lực giá")
    delivery_conditions = fields.Text(string="Điều kiện giao hàng")
    delivery_location = fields.Text(string="Địa điểm giao hàng")
    payment_term_days = fields.Float(string="Thời hạn thanh toán")
    payment_method = fields.Selection(
        selection=[
            ('tt','TT'),
            ('lc','LC'),
            ('dp','DP'),
            ('dap','DAP')
        ],
        string="Hình thức thanh toán"
    )
    deposit = fields.Float(string="Đặt cọc")
    warranty_conditions = fields.Text(string="Điều kiện bảo hành")
    warranty_period = fields.Text(string="Thời gian bảo hành")
    warranty_retention_rate = fields.Float(string="Tỷ lệ giữ lại bảo hành")
    warranty_settlement_period = fields.Text(string="Thời hạn tất toán bảo hành")
    penalty_late_delivery = fields.Text(string="Phạt giao chậm")
    penalty_late_payment = fields.Text(string="Phạt thanh toán chậm")
    penalty_breach_contract = fields.Text(string="Phạt vi phạm điều khoản hơp đồng chung")
    x_hard_contract = fields.Char(string="Số hợp đồng bản cứng")

    def sync_x_supplier_contract_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = """
            SELECT 
                name,
                x_supplier_id,
                x_date_from,
                x_date_to,
                x_delivery_time_estimate,
                state,
                x_contract_type,
                x_po_id,
                price_validity_conditions,
                delivery_conditions,
                delivery_location,
                payment_term_days,
                payment_method,
                deposit,
                warranty_conditions,
                warranty_period,
                warranty_retention_rate,
                warranty_settlement_period,
                penalty_late_delivery,
                penalty_late_payment,
                penalty_breach_contract,
                x_hard_contract
            FROM 
                x_supplier_contract
        """

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            for r in data:
                records_to_create.append({
                    'name' : r.get('name'),
                    # 'x_supplier_id' : r.get('x_supplier_id'),
                    'x_date_from' : r.get('x_date_from'),
                    'x_date_to' : r.get('x_date_to'),
                    'x_delivery_time_estimate' : r.get('x_delivery_time_estimate'),
                    'state' : r.get('state'),
                    'x_contract_type' : r.get('x_contract_type'),
                    # 'x_po_id' : r.get('x_po_id'),
                    'price_validity_conditions' : r.get('price_validity_conditions'),
                    'delivery_conditions' : r.get('delivery_conditions'),
                    'delivery_location' : r.get('delivery_location'),
                    'payment_term_days' : r.get('payment_term_days'),
                    'payment_method' : r.get('payment_method'),
                    'deposit' : r.get('deposit'),
                    'warranty_conditions' : r.get('warranty_conditions'),
                    'warranty_period' : r.get('warranty_period'),
                    'warranty_retention_rate' : r.get('warranty_retention_rate'),
                    'warranty_settlement_period' : r.get('warranty_settlement_period'),
                    'penalty_late_delivery' : r.get('penalty_late_delivery'),
                    'penalty_late_payment' : r.get('penalty_late_payment'),
                    'penalty_breach_contract' : r.get('penalty_breach_contract'),
                    'x_hard_contract' : r.get('x_hard_contract'),
                })

        if records_to_create:
            self.sudo().create(records_to_create)

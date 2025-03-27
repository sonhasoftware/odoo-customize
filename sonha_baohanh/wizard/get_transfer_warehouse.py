from odoo import api, models, fields

class GetTransferWarehouse(models.TransientModel):
    _name = 'get.transfer.warehouse'

    warranty_code = fields.Many2one('warranty.information', string="Mã bảo hành", domain="[('transfer_warehouse', '=', True)]")
    customer_name = fields.Char(string="Tên khách hàng", compute="fill_data_transfer_warehouse")
    customer_number = fields.Char(string="Số điện thoại", compute="fill_data_transfer_warehouse")
    address = fields.Text(string="Địa chỉ", compute="fill_data_transfer_warehouse")
    transfer_warehouse = fields.One2many('transfer.warehouse', 'warranty_code', string="Chuyển kho", compute="fill_data_transfer_warehouse")

    @api.depends('warranty_code')
    def fill_data_transfer_warehouse(self):
        for r in self:
            r.customer_name = r.warranty_code.customer_information if r.warranty_code.customer_information else ''
            r.customer_number = r.warranty_code.mobile_customer if r.warranty_code.mobile_customer else ''
            r.address = r.warranty_code.address if r.warranty_code.address else ''
            transfer_warehouse = self.env['transfer.warehouse'].sudo().search([('warranty_code', '=', r.warranty_code.id)])
            r.transfer_warehouse = transfer_warehouse if transfer_warehouse else False

    def action_confirm(self):
        list_records = self.env['transfer.warehouse'].sudo().search([('warranty_code', '=', self.warranty_code.id)])
        if list_records:
            for r in list_records:
                vals = {
                    'warranty_code': r.warranty_code.id,
                    'product_code': r.product_code.id,
                    'product_name': r.product_name,
                    'unit': r.unit,
                    'amount': r.receive_amount,
                    'branch_id': r.branch_id.id,
                }
                self.env['import.before.repair'].sudo().create(vals)
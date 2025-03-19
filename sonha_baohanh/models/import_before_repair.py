from odoo import api, fields, models

class ImportBeforeRepair(models.Model):
    _name = 'import.before.repair'

    warranty_code = fields.Many2one('warranty.information', string="ID bảo hành",
                                    domain="['|', ('import_company', '=', True), ('work', '=', 'non_assign')]")
    customer_name = fields.Char(string="Tên khách hàng", compute="fill_data_import", store=True)
    phone_number = fields.Char(string="Điện thoại")
    address = fields.Text(string="Địa chỉ")
    unit = fields.Char(string="ĐVT", compute="filter_product", store=True)
    amount = fields.Integer(string="Số lượng")
    produce_month = fields.Selection([('one', 1),
                                      ('two', 2),
                                      ('three', 3),
                                      ('four', 4),
                                      ('five', 5),
                                      ('six', 6),
                                      ('seven', 7),
                                      ('eight', 8),
                                      ('nine', 9),
                                      ('ten', 10),
                                      ('eleven', 11),
                                      ('twelve', 12)], string="Tháng sản xuất")
    produce_year = fields.Char(string="Năm sản xuất")
    error_infor = fields.Text(string="Tình trạng lỗi")
    input_content = fields.Text(string="Nội dung nhập")
    delivery_people = fields.Char(string="Người vận chuyển")
    branch_id = fields.Many2one('bh.branch', string="Chi nhánh")
    bh_create_date = fields.Datetime(string="Ngày nhập", default=fields.Datetime.now)
    product_code = fields.Many2one('sonha.product', string="Mã sản phẩm")
    product_name = fields.Char(string="Tên sản phẩm", compute="filter_product", store=True)
    warehouse = fields.Char(string="Mã kho nhập")
    plant = fields.Char(string="Plant")


    @api.depends('warranty_code')
    def fill_data_import(self):
        for r in self:
            if r.warranty_code:
                r.customer_name = r.warranty_code.customer_information if r.warranty_code.customer_information else ''
                r.phone_number = r.warranty_code.mobile_customer if r.warranty_code.mobile_customer else ''
                r.address = r.warranty_code.address if r.warranty_code.address else ''
                r.produce_month = r.warranty_code.produce_month if r.warranty_code.produce_month else ''
                r.produce_year = r.warranty_code.produce_year.name if r.warranty_code.produce_year else ''
                r.error_infor = r.warranty_code.error_cause if r.warranty_code.error_cause else ''
                r.branch_id = r.warranty_code.branch_id.id if r.warranty_code.branch_id else None
                if r.warranty_code.branch_id:
                    r.warehouse = r.warranty_code.branch_id.warehouse_tsc if r.warranty_code.branch_id.warehouse_tsc else ''
                    r.plant = r.warranty_code.branch_id.plant if r.warranty_code.branch_id.plant else ''
            else:
                r.customer_name = ''
                r.phone_number = ''
                r.address = ''
                r.produce_month = ''
                r.produce_year = ''
                r.error_infor = ''
                r.warehouse = ''
                r.plant = ''

    @api.depends('product_code')
    def filter_product(self):
        for r in self:
            if r.product_code:
                r.product_name = r.product_code.product_name if r.product_code.product_name else ''
                r.unit = r.product_code.unit if r.product_code.unit else ''
            else:
                r.product_name = ''
                r.unit = ''


    def create(self, vals):
        list_records = super(ImportBeforeRepair, self).create(vals)
        for record in list_records:
            vals = {
                'customer_name': record.customer_name,
                'phone_number': record.phone_number,
                'address': record.address,
                'warranty_code': record.warranty_code.id,
                'product_code': record.product_code.id,
                'product_name': record.product_name,
                'unit': record.unit,
                'request_amount': record.amount,
                'export_amount': record.amount,
                'branch_id': record.branch_id.id,
                'import_before_repair': record.id,
                'plant': record.plant
            }
            self.env['form.export.company.rel'].sudo().create(vals)
        return list_records

    def write(self, vals):
        res = super(ImportBeforeRepair, self).write(vals)
        for record in self:
            form_export = self.env['form.export.company.rel'].sudo().search([('import_before_repair', '=', record.id)])
            vals = {
                'customer_name': record.customer_name,
                'phone_number': record.phone_number,
                'address': record.address,
                'warranty_code': record.warranty_code.id,
                'product_code': record.product_code.id,
                'product_name': record.product_name,
                'unit': record.unit,
                'request_amount': record.amount,
                'export_amount': record.amount,
                'branch_id': record.branch_id.id,
                'import_before_repair': record.id,
                'plant': record.plant
            }
            if form_export:
                form_export.sudo().write(vals)
        return res

    def unlink(self):
        for r in self:
            removes = self.env['form.export.company.rel'].sudo().search([('import_before_repair', '=', r.id)])
            if removes:
                removes.sudo().unlink()
        return super(ImportBeforeRepair, self).unlink()




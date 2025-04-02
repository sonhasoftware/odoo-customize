from odoo import api, fields, models
from datetime import datetime, time, timedelta
from odoo.exceptions import UserError, ValidationError

class ExportCompany(models.Model):
    _name = 'export.company'

    export_date = fields.Date(string="Ngày xuất", default=fields.Datetime.now)
    delivery_note = fields.Char(string="Phếu xuất")
    employee_name = fields.Char(string="Họ và tên", default=lambda self: self.default_employee_name())
    address = fields.Text(string="Địa chỉ", compute="fillter_data")
    export_reason = fields.Text(string="Lý do xuất kho")
    warranty_code = fields.Many2one('warranty.information', string="ID",
                                    domain="[('warranty_status', '=', 'branch_warehouse')]")
    branch_id = fields.Many2one('bh.branch', string="Đơn vị", compute="fillter_data")
    product_code = fields.Char(string="Mã sản phẩm")
    product_name = fields.Char(string="Tên sản phẩm")
    export_warehouse = fields.Char(string="Mã kho xuất")
    unit = fields.Char(string="ĐVT")
    request_amount = fields.Integer(string="Số lượng yêu cầu")
    export_amount = fields.Integer(string="Số lượng thực xuất")
    note = fields.Text(string="Ghi chú")
    form_export_company = fields.One2many('form.export.company.rel', 'warranty_code', string="Sản phẩm", compute="_onchange_warranty_code", inverse="_inverse_data")

    @api.depends('warranty_code')
    def fillter_data(self):
        for r in self:
            r.address = r.warranty_code.address if r.warranty_code.address else ''
            r.branch_id = r.warranty_code.branch_id.id if r.warranty_code.branch_id.id else None

    @api.depends('warranty_code')
    def _onchange_warranty_code(self):
        for record in self:
            form_export_company = self.env['form.export.company.rel'].sudo().search([('warranty_code', '=', record.warranty_code.id)])
            record.form_export_company = form_export_company if form_export_company else False

    def _inverse_data(self):
        for r in self:
            if r.form_export_company:
                for record in r.form_export_company:
                    record.write({'product_code': record.product_code})

    def create(self, vals):
        record = super(ExportCompany, self).create(vals)
        current_year = datetime.now().year
        vals = {
            'delivery_note': f"{record.warranty_code.branch_id.plant}."
                             + f"{str(current_year)[-2:]}."
                             + f"{record.id:04d}" if record.warranty_code.branch_id.plant else ""
        }
        record.sudo().write(vals)
        warranty_infor = self.env['warranty.information'].sudo().search([('id', '=', record.warranty_code.id)])
        warranty_infor.sudo().write({'warranty_status': 'company_warehouse'})
        synthetic_data = self.env['form.export.company.rel'].sudo().search([('warranty_code', '=', record.warranty_code.id)])
        for data in synthetic_data:
            val = {
                'export_company_date': record.export_date,
                'delivery_note_to_com': record.delivery_note,
            }
            data.sudo().write(val)
        return record


    def write(self, vals):
        res = super(ExportCompany, self).write(vals)
        if 'warranty_code' in vals:
            raise ValidationError("Không được sửa mã bảo hành!")
        return res

    def unlink(self):
        for r in self:
            synthetic_data = self.env['form.export.company.rel'].sudo().search([('warranty_code', '=', r.warranty_code.id)])
            synthetic_data.sudo().write({'export_company_date': None,
                                         'delivery_note_to_com': ''})
            warranty_infor = self.env['warranty.information'].sudo().search([('id', '=', r.warranty_code.id)])
            warranty_infor.sudo().write({'warranty_status': 'branch_warehouse'})
        return super(ExportCompany, self).unlink()

    def default_employee_name(self):
        return self.env.user.name



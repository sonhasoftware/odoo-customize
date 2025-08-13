from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class DeclareMDSupplier(models.Model):
    _name = 'declare.md.supplier'
    _description = 'Khai báo data Nhà cung cấp'

    name = fields.Char("Tên nhà cung cấp")
    supp_code = fields.Char("Mã nhà cc")
    supp_phone = fields.Char("Điện thoại")
    tax_code = fields.Char("Mã số thuế")
    address = fields.Char("Địa chỉ")
    supp_type = fields.Many2one('bp.type', string="Loại đối tác kinh doanh")
    supp_group = fields.Many2one('bp.group.account', string="Nhóm NCC")
    company_id = fields.Many2one('res.company', string="Đơn vị")
    country_id = fields.Many2one('res.country', string='Quốc gia')
    state_id = fields.Many2one('res.country.state', string='Tỉnh thành', domain="[('country_id', '=', country_id)]")
    supp_class = fields.Selection([('domestic', "Trong nước"), ('abroad', "Nước ngoài")], string="Kiểu nhà cung cấp")
    status = fields.Selection([('draft', "Nháp"),
                               ('waiting', "Chờ duyệt"),
                               ('done', "Đã duyệt")], string="Trạng thái", default='draft')
    next_approve_employee = fields.Many2many('hr.employee', string="Người duyệt")
    district_id = fields.Many2one('config.district', string="Quận/Huyện", domain="[('state_id', '=', state_id)]")
    ward_id = fields.Many2one('config.ward', string="Phường/xã", domain="[('district_id', '=', district_id)]")

    postal_code = fields.Char("Mã bưu điện")
    mail_address = fields.Char("Email")
    old_vendor_code = fields.Char("Mã NCC trên hệ thống khác")
    language = fields.Char("Ngôn ngữ", default="EN")
    fax_number = fields.Char("Số Fax")
    bank_number = fields.Char("Số tài khoản ngân hàng")
    bank_owner = fields.Char("Chủ tài khoản")
    bank_country_code = fields.Many2one('bank.country', string="Mã quốc gia")
    bank_key = fields.Many2one('bank.data', string="Ngân hàng", domain="[('bank_country', '=', bank_country_code)]")
    industry = fields.Many2one('vendor.industry', string="Loại NCC(SX/TM)")
    form_of_org = fields.Many2one('form.organization', string="Hình thức sở hữu doanh nghiệp")
    deposit_proportion = fields.Char("Tỷ lệ đặt cọc")

    trading_partner = fields.Many2one('trading.partner', string="Công ty nội bộ")
    company_code = fields.Many2one('company.code', "Mã công ty", required=True)
    customer_code = fields.Char("Mã khách hàng")
    reconciliation_account = fields.Many2one('reconciliation.account', string="Tài khoản kế toán")
    planning_group = fields.Many2one('planning.group', string="Mã dự báo dòng tiền")
    payment_term = fields.Many2one('payment.term', string="Điều khoản thanh toán")
    double_invoice = fields.Boolean("Kiểm tra hóa đơn trùng", default=True)
    payment_method = fields.Many2many('cus.payment.method', string="Phương thức thanh toán")
    clear_debt = fields.Boolean("Khấu trừ công nợ")
    previous_num = fields.Char("Mã NCC cũ")
    vendor_block = fields.Boolean("Khóa nhà cung cấp")

    employee_id = fields.Many2one('hr.employee', string="Người tạo", default=lambda self: self.get_create_employee())
    md_approve_display = fields.One2many('md.approve.display', 'md_supplier', string="Quy trình duyệt")

    vendor_purchase = fields.One2many('vendor.purchase', 'declare_vendor')

    @api.onchange('company_id')
    def onchange_company_code(self):
        for r in self:
            if r.company_id:
                code = self.env['company.code'].sudo().search([('company_id', '=', r.company_id.id)])
                if code:
                    r.company_code = code.id
                else:
                    r.company_code = None

    def get_create_employee(self):
        employee = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.uid)])
        if employee:
            return employee.id

    def get_approve_people(self, record, employee):
        admin = self.env['hr.employee'].sudo().search([('id', '=', 1)])
        approve_people = admin
        employee_id = self.env['hr.employee'].sudo().search([('id', '=', employee.id)])
        if record.method == 'role':
            if record.approve_role and record.approve_role.approve_employee:
                approve_people = record.approve_role.approve_employee
        elif record.method == 'assign':
            if record.employee_id:
                approve_people = record.employee_id
        elif record.method == 'parent':
            if employee_id.parent_id:
                approve_people = employee_id.parent_id
        else:
            if employee_id.department_id and employee_id.department_id.manager_id:
                approve_people = employee_id.department_id.manager_id
        return approve_people

    def get_approve_employee(self):
        for r in self:
            list_suggest = r.md_approve_display.filtered(lambda x: x.level == 'suggest' and x.status == 'waiting')
            if list_suggest and r.status == 'draft':
                next_approve_people = list_suggest.mapped('employee_id')
            else:
                list_approve = r.md_approve_display.filtered(lambda x: x.level not in ['suggest', 'examine', 'notice'] and x.status == 'waiting')
                list_approve = list_approve.sorted(key=lambda x: (x.sequence_step, x.id))
                next_approve_people = list_approve[0].employee_id
            return next_approve_people

    def action_approve(self):
        for r in self:
            if r.status == 'waiting':
                if self.env.user.employee_ids in r.next_approve_employee or self.env.uid == 2:
                    list_approve = r.md_approve_display.filtered(lambda x: x.level not in ['examine', 'notice'] and x.status == 'waiting')
                    if len(list_approve) == 1:
                        r.status = 'done'
                        list_approve[0].sudo().write({'status': 'done'})
                        code = f"NCC{r.id:06d}"
                        r.supp_code = code
                        vals = {
                            'supp_code': code,
                            'name': r.name,
                            'supp_phone': r.supp_phone,
                            'tax_code': r.tax_code,
                            'address': r.address,
                            'supp_type': r.supp_type.id,
                            'bp_group_account': r.supp_group.id,
                            'company_id': r.company_id.id,
                            'country_id': r.country_id.id,
                            'state_id': r.state_id.id,
                            'supp_class': r.supp_class,
                            'district_id': r.district_id.id,
                            'ward_id': r.ward_id.id,
                            'declare_supplier': r.id,
                            'trading_partner': r.trading_partner.id,
                            'reconciliation_account': r.reconciliation_account.id,
                            'planning_group': r.planning_group.id,
                            'payment_term': r.payment_term.id,
                            'payment_method': [(6, 0, r.payment_method.ids)],
                            'double_invoice': r.double_invoice,
                            'clear_debt': r.clear_debt,
                            'postal_code': r.postal_code,
                            'mail_address': r.mail_address,
                            'old_vendor_code': r.old_vendor_code,
                            'language': r.language,
                            'fax_number': r.fax_number,
                            'bank_number': r.bank_number,
                            'bank_owner': r.bank_owner,
                            'deposit_proportion': r.deposit_proportion,
                            'bank_country_code': r.bank_country_code.id,
                            'bank_key': r.bank_key.id,
                            'industry': r.industry.id,
                            'form_of_org': r.form_of_org.id,
                            'customer_code': r.customer_code,
                            'company_code': r.company_code.id,
                            'vendor_block': r.vendor_block,
                        }
                        md = self.env['md.supplier'].sudo().create(vals)
                        vendor_purchase = self.env['vendor.purchase'].sudo().search([('declare_vendor', '=', r.id)])
                        if vendor_purchase:
                            vendor_purchase.sudo().write({'md_vendor': md.id})
                    else:
                        list_suggest = r.md_approve_display.filtered(lambda x: x.level == 'suggest' and x.status == 'waiting')
                        if list_suggest:
                            list_suggest.sudo().write({'status': 'done'})
                        else:
                            list_approve[0].sudo().write({'status': 'done'})
                        next_approve_people = r.get_approve_employee()
                        r.next_approve_employee = next_approve_people
                else:
                    raise ValidationError("Bạn không có quyền duyệt bước này!")
            else:
                raise ValidationError("Bạn không thể duyệt bản ghi này!")

    def action_sent(self):
        for r in self:
            if r.employee_id.user_id.id == self.env.uid or self.env.uid == 2:
                model_id = self.env['ir.model'].sudo().search([('model', '=', 'declare.md.supplier')], limit=1).id
                approve_rule = self.env['md.approve.rule'].sudo().search([('model_apply', '=', model_id),
                                                                          ('company_ids', 'in', r.company_id.id)])
                if approve_rule:
                    for record in approve_rule.step:
                        approve_emp = self.get_approve_people(record, r.employee_id)
                        val = {
                            'sequence_step': record.sequence_step,
                            'level': record.level,
                            'employee_id': approve_emp.id,
                            'md_supplier': r.id,
                        }
                        self.env['md.approve.display'].sudo().create(val)
                    approve_record = approve_rule.step.filtered(lambda x: x.level not in ['suggest', 'examine', 'notice'])
                    if not approve_record:
                        admin = self.env['hr.employee'].sudo().search([('id', '=', 1)])
                        val = {
                            'sequence_step': len(approve_rule.step) + 1,
                            'level': 'approve',
                            'employee_id': admin.id,
                            'md_supplier': r.id,
                        }
                        self.env['md.approve.display'].sudo().create(val)
                else:
                    admin = self.env['hr.employee'].sudo().search([('id', '=', 1)])
                    val = {
                        'sequence_step': 1,
                        'level': 'approve',
                        'employee_id': admin.id,
                        'md_supplier': r.id,
                    }
                    self.env['md.approve.display'].sudo().create(val)
                r.next_approve_employee = r.get_approve_employee()
                r.status = 'waiting'
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

    def to_draft_action(self):
        for r in self:
            if self.env.user.employee_ids in r.next_approve_employee or self.env.uid == 2:
                r.next_approve_employee = None
                r.status = 'draft'
                r.supp_code = ""
                record = self.env['md.supplier'].sudo().search([('declare_supplier', '=', r.id)])
                if record:
                    record.sudo().unlink()
                self.env['md.approve.display'].sudo().search([('md_supplier', '=', r.id)]).unlink()
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

    def multi_approval(self):
        for r in self:
            r.action_approve()

    def unlink(self):
        for r in self:
            if r.status != 'draft':
                raise ValidationError("Chỉ được xóa khi là ở trạng thái nháp!")
            self.env['vendor.purchase'].sudo().search([('declare_vendor', '=', r.id)]).unlink()
        return super(DeclareMDSupplier, self).unlink()

    @api.constrains('tax_code')
    def validate_record(self):
        if self.tax_code:
            exist_tax_code = self.env['declare.md.supplier'].sudo().search([('id', '!=', self.id),
                                                                            ('tax_code', '=', self.tax_code)])
        if exist_tax_code:
            raise ValidationError("Đã có khách hàng với số căng cước hoặc mã số thuế này rồi!")

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class DeclareMDCustomer(models.Model):
    _name = 'declare.md.customer'
    _description = 'Khai báo data Khách hàng'
    _rec_name = 'customer_name'

    customer_code = fields.Char("Mã khách hàng")
    customer_name = fields.Char("Tên khách hàng", required=True, size=80)
    cust_phone = fields.Char("Số điện thoại", size=30)
    address = fields.Char("Địa chỉ khách", required=True, size=115)
    tax_code = fields.Char("Mã số thuế", size=20)
    company_id = fields.Many2one('res.company', string="Đơn vị", required=True)
    bp_type_id = fields.Many2one('bp.type', string="Loại đối tác kinh doanh")
    customer_group_id = fields.Many2one('bp.group.account', string="Nhóm phân loại khách hàng", required=True)
    country_id = fields.Many2one('res.country', string='Quốc gia', required=True)
    state_id = fields.Many2one('res.country.state', string='Tỉnh thành',
                               domain="[('country_id', '=', country_id)]", required=True)
    customer_class = fields.Selection([('domestic', "Trong nước"), ('abroad', "Nước ngoài")], string="Kiểu khách hàng")
    status = fields.Selection([('draft', "Nháp"),
                               ('waiting', "Chờ duyệt"),
                               ('done', "Đã duyệt")], string="Trạng thái", default='draft')
    district_id = fields.Many2one('config.district', string="Quận/Huyện", domain="[('state_id', '=', state_id)]")
    ward_id = fields.Many2one('config.ward', string="Phường/xã", domain="[('district_id', '=', district_id)]")
    cccd_number = fields.Char("Số cccd")
    legal_representative = fields.Char("Đại diện pháp lý")
    mail_address = fields.Char("Email")
    old_customer_code = fields.Char("Mã khách hàng cũ")

    next_approve_employee = fields.Many2many('hr.employee', string="Người duyệt")
    employee_id = fields.Many2one('hr.employee', string="Người tạo", default=lambda self: self.get_create_employee())
    md_approve_display = fields.One2many('md.approve.display', 'md_customer', string="Quy trình duyệt")

    postal_code = fields.Char("Mã bưu điện")
    language = fields.Char("Ngôn ngữ", default="EN", required=True)
    fax_number = fields.Char("Số Fax")
    bank_number = fields.Char("Số tài khoản ngân hàng")
    bank_owner = fields.Char("Chủ tài khoản")
    sale_man = fields.Many2one('declare.md.saleman', "Nhân viên kinh doanh")
    region_manager = fields.Many2one('declare.md.saleman', "Quản lý vùng")
    area_manager = fields.Many2one('declare.md.saleman', "Quản lý khu vực")
    bank_country_code = fields.Many2one('bank.country', string="Mã quốc gia")
    bank_key = fields.Many2one('bank.data', string="Ngân hàng", domain="[('bank_country', '=', bank_country_code)]")

    company_code = fields.Many2one('company.code', "Mã công ty", required=True)
    vendor_code = fields.Char("Mã NCC liên kết")
    trading_partner = fields.Many2one('trading.partner', string="Công ty nội bộ")
    reconciliation_account = fields.Many2one('reconciliation.account', string="Tài khoản kế toán", required=True)
    payment_term = fields.Many2one('payment.term', string="Điều khoản thanh toán", required=True)
    payment_method = fields.Many2many('cus.payment.method', string="Phương thức thanh toán")

    customer_sale = fields.One2many('customer.sale', 'declare_md_customer')

    credit_limit = fields.One2many('credit.limit', 'declare_customer')

    relationship = fields.One2many('emp.relationship', 'declare_customer')

    check_cccd_number = fields.Boolean()
    check_tax_code = fields.Boolean()

    name_1 = fields.Char(compute="compute_split_name", store=True)
    name_2 = fields.Char(compute="compute_split_name", store=True)
    name_3 = fields.Char(compute="compute_split_name", store=True)

    address_1 = fields.Char(compute="compute_split_address", store=True)
    address_2 = fields.Char(compute="compute_split_address", store=True)
    address_3 = fields.Char(compute="compute_split_address", store=True)

    customer_short_name = fields.Char("Tên ngắn gọn", size=25, required=True)
    search_term = fields.Char("Mã tìm kiếm nhanh", size=20)
    search_term_2 = fields.Char("Mã NCC trên Odoo", size=20)

    @api.onchange('company_id')
    def onchange_company_code(self):
        for r in self:
            if r.company_id:
                code = self.env['company.code'].sudo().search([('company_id', '=', r.company_id.id)])
                if code:
                    r.company_code = code.id
                else:
                    r.company_code = None

    @api.depends('customer_name')
    def compute_split_name(self):
        for r in self:
            if r.customer_name:
                name = r.customer_name
                result = []
                while name != "":
                    split_pos = name.rfind(' ', 0, 40)
                    if split_pos == -1 or len(name) <= 40:
                        sort_name = name[:40]
                        name = name[40:]
                        result.append(sort_name)
                    else:
                        sort_name = name[:split_pos]
                        name = name[split_pos+1:].lstrip()
                        result.append(sort_name)
                while len(result) < 3:
                    result.append("")
                r.name_1 = result[0]
                r.name_2 = result[1]
                r.name_3 = result[2]

    @api.depends('address')
    def compute_split_address(self):
        for r in self:
            if r.address:
                address = r.address
                result = []
                turn = 1
                while address != "":
                    if turn < 2:
                        block = 35
                    else:
                        block = 40
                    split_pos = address.rfind(' ', 0, block)
                    if split_pos == -1 or len(address) <= block:
                        sort_address = address[:block]
                        address = address[block:]
                        result.append(sort_address)
                    else:
                        sort_address = address[:split_pos]
                        address = address[split_pos + 1:].lstrip()
                        result.append(sort_address)
                    turn += 1
                while len(result) < 3:
                    result.append("")
                r.address_1 = result[0]
                r.address_2 = result[1]
                r.address_3 = result[2]

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
                        list_approve[0].sudo().write({'status': 'done'})
                        code = f"KH{r.id:06d}"
                        r.status = 'done'
                        r.customer_code = code
                        vals = {
                            'customer_code': code,
                            'customer_name': r.customer_name,
                            'cust_phone': r.cust_phone,
                            'address': r.address,
                            'tax_code': r.tax_code,
                            'company_id': r.company_id.id,
                            'customer_type_id': r.bp_type_id.id,
                            'customer_group_id': r.customer_group_id.id,
                            'country_id': r.country_id.id,
                            'state_id': r.state_id.id,
                            'customer_class': r.customer_class,
                            'district_id': r.district_id.id,
                            'ward_id': r.ward_id.id,
                            'cccd_number': r.cccd_number,
                            'legal_representative': r.legal_representative,
                            'mail_address': r.mail_address,
                            'old_customer_code': r.old_customer_code,
                            'declare_customer': r.id,
                            'postal_code': r.postal_code,
                            'language': r.language,
                            'fax_number': r.fax_number,
                            'bank_number': r.bank_number,
                            'bank_owner': r.bank_owner,
                            'sale_man': r.sale_man.id,
                            'region_manager': r.region_manager,
                            'area_manager': r.area_manager,
                            'company_code': r.company_code.id,
                            'vendor_code': r.vendor_code,
                            'bank_country_code': r.bank_country_code.id,
                            'bank_key': r.bank_key.id,
                            'trading_partner': r.trading_partner.id,
                            'reconciliation_account': r.reconciliation_account.id,
                            'payment_term': r.payment_term.id,
                            'payment_method': [(6, 0, r.payment_method.ids)],
                            'customer_short_name': r.customer_short_name,
                            'search_term': r.search_term,
                            'search_term_2': r.search_term_2,
                        }
                        md = self.env['md.customer'].sudo().create(vals)
                        sale = self.env['customer.sale'].sudo().search([('declare_md_customer', '=', r.id)])
                        credit = self.env['credit.limit'].sudo().search([('declare_customer', '=', r.id)])
                        relation = self.env['emp.relationship'].sudo().search([('declare_customer', '=', r.id)])
                        sale.sudo().write({'md_customer': md.id})
                        credit.sudo().write({'md_customer': md.id})
                        relation.sudo().write({'md_customer': md.id})
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
                model_id = self.env['ir.model'].sudo().search([('model', '=', 'declare.md.customer')], limit=1).id
                approve_rule = self.env['md.approve.rule'].sudo().search([('model_apply', '=', model_id),
                                                                          ('company_ids', 'in', r.company_id.id)])
                if approve_rule:
                    for record in approve_rule.step:
                        approve_emp = self.get_approve_people(record, r.employee_id)
                        val = {
                            'sequence_step': record.sequence_step,
                            'level': record.level,
                            'employee_id': approve_emp.id,
                            'md_customer': r.id,
                        }
                        self.env['md.approve.display'].sudo().create(val)
                    approve_record = approve_rule.step.filtered(lambda x: x.level not in ['suggest', 'examine', 'notice'])
                    if not approve_record:
                        admin = self.env['hr.employee'].sudo().search([('id', '=', 1)])
                        val = {
                            'sequence_step': len(approve_rule.step) + 1,
                            'level': 'approve',
                            'employee_id': admin.id,
                            'md_customer': r.id,
                        }
                        self.env['md.approve.display'].sudo().create(val)
                else:
                    admin = self.env['hr.employee'].sudo().search([('id', '=', 1)])
                    val = {
                        'sequence_step': 1,
                        'level': 'approve',
                        'employee_id': admin.id,
                        'md_customer': r.id,
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
                r.customer_code = ""
                record = self.env['md.customer'].sudo().search([('declare_customer', '=', r.id)])
                if record:
                    record.sudo().unlink()
                self.env['md.approve.display'].sudo().search([('md_customer', '=', r.id)]).unlink()
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

    def multi_approval(self):
        for r in self:
            r.action_approve()

    def unlink(self):
        for r in self:
            if r.status != 'draft':
                raise ValidationError("Chỉ được xóa khi là ở trạng thái nháp!")
            else:
                self.env['customer.sale'].sudo().search([('declare_md_customer', '=', r.id)]).unlink()
                self.env['credit.limit'].sudo().search([('declare_customer', '=', r.id)]).unlink()
                self.env['emp.relationship'].sudo().search([('declare_customer', '=', r.id)]).unlink()
        return super(DeclareMDCustomer, self).unlink()

    def validate_record(self, record):
        validate = 0
        if record.cccd_number:
            exist_cccd = self.env['declare.md.customer'].sudo().search([('id', '!=', record.id),
                                                                        ('cccd_number', '=', record.cccd_number)])
            if exist_cccd:
                validate = 1
        if record.tax_code:
            exist_tax_code = self.env['declare.md.customer'].sudo().search([('id', '!=', record.id),
                                                                            ('tax_code', '=', record.tax_code)])
            if exist_tax_code:
                validate = 1
        if validate == 1:
            raise ValidationError("Đã có khách hàng với số căng cước hoặc mã số thuế này rồi!")

    def create(self, vals):
        res = super(DeclareMDCustomer, self).create(vals)
        self.validate_record(res)
        return res

    def write(self, vals):
        res = super(DeclareMDCustomer, self).write(vals)
        if ('cccd_number' in vals) or ('tax_code' in vals):
            for r in self:
                self.validate_record(r)
        return res

    @api.onchange('tax_code')
    def require_cccd_number(self):
        for r in self:
            if r.tax_code:
                r.check_tax_code = True
            else:
                r.check_tax_code = False

    @api.onchange('cccd_number')
    def require_tax_code(self):
        for r in self:
            if r.cccd_number:
                r.check_cccd_number = True
            else:
                r.check_cccd_number = False



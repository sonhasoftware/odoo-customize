from odoo import models, fields, _

# các trường comment là cần thiết nhưng chưa liên kết với model
class ResPartnerCustom(models.Model):
    _name = 'res.partner.custom'

    name = fields.Char(string="Name")
    # company_id = fields.Many2one('res.company',string="Company")
    date = fields.Date(string="Date")
    # title = fields.Many2one('res.partner.title',string="title")
    # parent_id = fields.Many2one('res.partner',string="Related Company")
    ref = fields.Char(string="Reference")
    # lang = fields.Selection(
    #     selection=[
    #         # không thấy lựa chọn trong field
    #     ],
    #     string="Language"
    # )
    # tz = fields.Selection(
    #     selection=[
    #         #no selection
    #     ],
    #     string="Timezone"
    # )
    # user_id = fields.Many2one('res.users',string="Salesperson")
    vat = fields.Char(string="VAT/Tax ID")
    website = fields.Char(string="Website Link")
    comment = fields.Html(string="Notes")
    credit_limit = fields.Float(string="Credit Limit")
    active = fields.Boolean(string="Active")
    employee = fields.Boolean(string="Employee")
    function = fields.Char(string="Job Position")
    type = fields.Selection(
        selection=[
            ('contact','Contact'),
            ('invoice','Invoice Address'),
            ('delivery','Delivery Address'),
            ('other','Other Address'),
            ('private','Private Address'),
        ],
        string="Address  Type"
    )
    street = fields.Char(string="Street")
    street2 = fields.Char(string="Street2")
    zip = fields.Char(string="Zip")
    city = fields.Char(string="City")
    # state_id = fields.Many2one('res.country.state',string="State")
    # country_id = fields.Many2one('res.country',string="Country")
    partner_latitude = fields.Float(string="Geo Latitude")
    partner_longitude = fields.Float(string="Geo Longitude")
    email = fields.Char(string="Email")
    phone = fields.Char(string="Phone")
    mobile = fields.Char(string="Mobile")
    is_company = fields.Boolean(string="Is a Company")
    # industry_id = fields.Many2one('res.partner.industry',string="Industry")
    color = fields.Integer(string="Color Index")
    partner_share = fields.Boolean(string="Share Partner")
    # commercial_partner_id = fields.Many2one('res.partner',string="Commercial Entity")
    commercial_company_name = fields.Char(string="Commercial Name Entity")
    company_name = fields.Char(string="Company Name")
    email_normalized = fields.Char(string="Normalized Email")
    message_bounce = fields.Integer(string="Bounce")
    signup_token = fields.Char(string="Signup Token")
    signup_type = fields.Char(string="Signup Type")
    signup_expiration = fields.Datetime(string="Signup Expiration")
    phone_sanitized = fields.Char(string="Sanitized Number")
    # debit_limit = fields.Monetary(string="Payable Limit")
    last_time_entries_checked = fields.Datetime(string="Latest Invoice&Payment Matching Date")
    invoice_warn = fields.Selection(
        selection=[
            ('no-message','No Message'),
            ('warning','Warning'),
            ('block','Blocking Message'),
        ],
        string="Invoice"
    )
    invoice_warn_msg = fields.Text(string="Message for Invoice")
    supplier_rank = fields.Integer(string="Supplier Rank")
    customer_rank = fields.Integer(string="Customer Rank")
    purchase_warn = fields.Selection(
        selection=[
            ('no-message', 'No Message'),
            ('warning', 'Warning'),
            ('block', 'Blocking Message'),
        ],
        string="Purchase Order"
    )
    purchase_warn_msg = fields.Text(string="Message for Purchase Order")
    picking_warn = fields.Selection(
        selection=[
            ('no-message', 'No Message'),
            ('warning', 'Warning'),
            ('block', 'Blocking Message'),
        ],
        string="Stock Picking"
    )
    picking_warn_msg = fields.Text(string="Message for Stock Picking")
    # team_id = fields.Many2one('crm.team',string="Sales Team")
    sale_warn = fields.Selection(
        selection=[
            ('no-message', 'No Message'),
            ('warning', 'Warning'),
            ('block', 'Blocking Message'),
        ],
        string="Sales Wanring"
    )
    sale_warn_msg = fields.Text(string="Message for Sales Order")
    x_partner_ref = fields.Char(string="Mã NCC")
    file_registration_name = fields.Char(string="File Name")
    x_is_supplier = fields.Boolean(string="Là Nhà cung cấp")
    x_erp_code = fields.Char(string="Mã số DN")
    # x_representative = fields.Many2one('res.partner',string="NDD")
    # x_supplier_type = fields.Many2one('res.supplier.type',string="Loại nhà cung cấp")
    # x_erp_form = fields.Many2one('x.erp.form',string="Hình thức chủ sở hữu doanh nghiệp")
    # x_erp_stock_type = fields.Many2one('x.erp.stock.type',string="Phân loại hàng hóa")
    # x_contract_id = fields.Many2one('x.supplier.contract',string="Hợp đồng hiệu lực")
    # x_user_bcu = fields.Many2one('res.users',string="Nhân sự BCU phụ trách")
    x_user_bcu_phone = fields.Char(string="Di động nhân sự phụ trách")
    # x_manager_bcu = fields.Many2one('res.users',string="Lãnh đạo BCU phụ trách")
    x_manager_bcu_phone = fields.Char(string="Di động lãnh đạo phụ trách")
    x_full_name = fields.Char(string="Tên đầy đủ")
    x_ncc_old = fields.Char(string="Mã NCC cũ")
    # x_supplier = fields.Many2one('x.supplier',string="Nhóm NCC")
    # x_purchase_org = fields.Many2one('x.purchase.org',string="Tổ chức mua hàng")
    x_purchase_limitation = fields.Boolean(string="Khóa NCC mức mua hàng")
    x_representatives = fields.Char(string="Người đại diện")
    # x_purchase_group = fields.Many2one('x.purchase.group',string="Nhóm mua hàng")
    # x_incoterm = fields.Many2one('x.incoterm',string="Incoterm")
    x_incoterm_note = fields.Char(string="Incoterm diễn giải")
    x_ship_date_count = fields.Float(string="Thời gian giao hàng (ngày)")
    # x_from_company = fields.Many2one('res.company',string="Plant này thuộc công ty")
    x_is_sap = fields.Boolean(string="SAP Transfer")
    x_supplier_is_internal = fields.Boolean(string="Là NCC nội bộ")

    def sync_res_partner_custom_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = """
            SELECT 
                id,
                name,
                company_id,
                date,
                title,
                parent_id,
                ref,
                lang,
                tz,
                user_id,
                vat,
                website,
                comment,
                credit_limit,
                active,
                employee,
                function,
                type,
                street,
                street2,
                zip,
                city,
                state_id,
                country_id,
                partner_latitude,
                partner_longitude,
                email,
                phone,
                mobile,
                is_company,
                industry_id,
                color,
                partner_share,
                commercial_partner_id,
                commercial_company_name,
                company_name,
                email_normalized,
                message_bounce,
                signup_token,
                signup_type,
                signup_expiration,
                phone_sanitized,
                debit_limit,
                last_time_entries_checked,
                invoice_warn,
                invoice_warn_msg,
                supplier_rank,
                customer_rank,
                purchase_warn,
                purchase_warn_msg,
                picking_warn,
                picking_warn_msg,
                team_id,
                sale_warn,
                sale_warn_msg,
                x_partner_ref,
                file_registration_name,
                x_is_supplier,
                x_erp_code,
                x_representative,
                x_supplier_type,
                x_erp_form,
                x_erp_stock_type,
                x_contract_id,
                x_user_bcu,
                x_user_bcu_phone,
                x_manager_bcu,
                x_manager_bcu_phone,
                x_full_name,
                x_ncc_old,
                x_supplier,
                x_purchase_org,
                x_purchase_limitation,
                x_representatives,
                x_purchase_group,
                x_incoterm,
                x_incoterm_note,
                x_ship_date_count,
                x_from_company,
                x_is_sap,
                x_supplier_is_internal
            FROM 
                res_partner
        """

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            self.with_context(active_test=False).sudo().search([]).unlink()
            for r in data:
                records_to_create.append({
                    'name' : r.get('name'),
                    # 'company_id' : r.get('company_id'),
                    'date' : r.get('date'),
                    # 'title' : r.get('title'),
                    # 'parent_id' : r.get('parent_id'),
                    'ref' : r.get('ref'),
                    # 'lang' : r.get('lang'),
                    # 'tz' : r.get('tz'),
                    # 'user_id' : r.get('user_id'),
                    'vat' : r.get('vat'),
                    'website' : r.get('website'),
                    'comment' : r.get('comment'),
                    'credit_limit' : r.get('credit_limit'),
                    'active' : r.get('active'),
                    'employee' : r.get('employee'),
                    'function' : r.get('function'),
                    'type' : r.get('type'),
                    'street' : r.get('street'),
                    'street2' : r.get('street2'),
                    'zip' : r.get('zip'),
                    'city' : r.get('city'),
                    # 'state_id' : r.get('state_id'),
                    # 'country_id' : r.get('country_id'),
                    'partner_latitude' : r.get('partner_latitude'),
                    'partner_longitude' : r.get('partner_longitude'),
                    'email' : r.get('email'),
                    'phone' : r.get('phone'),
                    'mobile' : r.get('mobile'),
                    'is_company' : r.get('is_company'),
                    # 'industry_id' : r.get('industry_id'),
                    'color' : r.get('color'),
                    'partner_share' : r.get('partner_share'),
                    # 'commercial_partner_id' : r.get('commercial_partner_id'),
                    'commercial_company_name' : r.get('commercial_company_name'),
                    'company_name' : r.get('company_name'),
                    'email_normalized' : r.get('email_normalized'),
                    'message_bounce' : r.get('message_bounce'),
                    'signup_token' : r.get('signup_token'),
                    'signup_type' : r.get('signup_type'),
                    'signup_expiration' : r.get('signup_expiration'),
                    'phone_sanitized' : r.get('phone_sanitized'),
                    # 'debit_limit' : r.get('debit_limit'),
                    'last_time_entries_checked' : r.get('last_time_entries_checked'),
                    'invoice_warn' : r.get('invoice_warn'),
                    'invoice_warn_msg' : r.get('invoice_warn_msg'),
                    'supplier_rank' : r.get('supplier_rank'),
                    'customer_rank' : r.get('customer_rank'),
                    'purchase_warn' : r.get('purchase_warn'),
                    'purchase_warn_msg' : r.get('purchase_warn_msg'),
                    'picking_warn' : r.get('picking_warn'),
                    'picking_warn_msg' : r.get('picking_warn_msg'),
                    # 'team_id' : r.get('team_id'),
                    'sale_warn' : r.get('sale_warn'),
                    'sale_warn_msg' : r.get('sale_warn_msg'),
                    'x_partner_ref' : r.get('x_partner_ref'),
                    'file_registration_name' : r.get('file_registration_name'),
                    'x_is_supplier' : r.get('x_is_supplier'),
                    'x_erp_code' : r.get('x_erp_code'),
                    # 'x_representative' : r.get('x_representative'),
                    # 'x_supplier_type' : r.get('x_supplier_type'),
                    # 'x_erp_form' : r.get('x_erp_form'),
                    # 'x_erp_stock_type' : r.get('x_erp_stock_type'),
                    # 'x_contract_id' : r.get('x_contract_id'),
                    # 'x_user_bcu' : r.get('x_user_bcu'),
                    'x_user_bcu_phone' : r.get('x_user_bcu_phone'),
                    # 'x_manager_bcu' : r.get('x_manager_bcu'),
                    'x_manager_bcu_phone' : r.get('x_manager_bcu_phone'),
                    'x_full_name' : r.get('x_full_name'),
                    'x_ncc_old' : r.get('x_ncc_old'),
                    # 'x_supplier' : r.get('x_supplier'),
                    # 'x_purchase_org' : r.get('x_purchase_org'),
                    'x_purchase_limitation' : r.get('x_purchase_limitation'),
                    'x_representatives' : r.get('x_representatives'),
                    # 'x_purchase_group' : r.get('x_purchase_group'),
                    # 'x_incoterm' : r.get('x_incoterm'),
                    'x_incoterm_note' : r.get('x_incoterm_note'),
                    'x_ship_date_count' : r.get('x_ship_date_count'),
                    # 'x_from_company' : r.get('x_from_company'),
                    'x_is_sap' : r.get('x_is_sap'),
                    'x_supplier_is_internal' : r.get('x_supplier_is_internal'),
                })

        if records_to_create:
            created_records = self.sudo().create(records_to_create)

            for record, r in zip(created_records, data):
                self.env.cr.execute("""
                            UPDATE {} 
                            SET id = %s 
                            WHERE id = %s
                        """.format(self._table), (r.get('id'), record.id))
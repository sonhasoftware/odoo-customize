from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, time, timedelta


class ExpContract(models.Model):
    _name = 'exp.contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'contract_no'
    _order = 'created_date desc, id desc'

    contract_no = fields.Char(string="Số hợp đồng", required=True, store=True, tracking=True)
    customer_id = fields.Many2one('exp.customer', string="Khách hàng", store=True, tracking=True)
    state_id = fields.Many2one('exp.contract.state',
                               group_expand="_read_group_state_ids",
                               default=lambda self: self.default_contract_state(),
                               required=True, string="Trạng thái", store=True, tracking=True)
    po_number = fields.Char(string="Số PO", store=True, tracking=True)
    total_amount = fields.Float(string="Tổng tiền", required=True, store=True, tracking=True)
    deposit_percent = fields.Float(string="% cọc", required=True, store=True, tracking=True)
    deposit_amount = fields.Float(string="Tiền cọc", required=True, store=True, tracking=True)
    currency = fields.Many2one('exp.config.currency', string="Tiền tệ", store=True, tracking=True)
    sign_date = fields.Date(string="Ngày ký hợp đồng", required=True, store=True, tracking=True)
    lc_required = fields.Boolean(string="Bản LC", required=True, store=True, tracking=True)
    lc_file = fields.Many2many('ir.attachment',
                               'exp_contract_lc_attachment_rel',
                               'contract_id',
                               'attachment_id', string="File điều kiện LC", store=True)
    lc_file_name = fields.Char(string="Tên file điều kiện LC", store=True)
    created_by = fields.Many2one('res.users', string="Người tạo",
                                 default=lambda self: self.env.user, required=True, store=True)
    created_date = fields.Date(string="Ngày tạo",
                               default=fields.Date.context_today, required=True, store=True)
    shipping = fields.Text(string="Vận chuyển", required=True, store=True, tracking=True)
    payment = fields.Text(string="Thanh toán", required=True, store=True, tracking=True)
    shipping_port_from = fields.Many2one('exp.config.port', string="Cảng bốc hàng",
                                         domain="[('type', '=', 'port_form')]", store=True, tracking=True)
    shipping_port_to = fields.Many2one('exp.config.port', string="Cảng dỡ hàng",
                                       domain="[('type', '=', 'port_to')]", store=True, tracking=True)
    shipping_time = fields.Date(string="Thời gian", store=True, tracking=True)
    shipping_country = fields.Many2one('exp.config.country', string="Quốc gia",
                                       compute="_get_country", store=True, tracking=True)
    payment_term = fields.Many2one('exp.config.term', string="Điều khoản thanh toán", store=True, tracking=True)
    bank = fields.Many2one('exp.config.bank', string="Ngân hàng", store=True, tracking=True)
    payment_note = fields.Text(string="Ghi chú thêm khác", store=True, tracking=True)
    note = fields.Text(string="Ghi chú", store=True, tracking=True)
    cont_request = fields.Integer(string="Số lượng CONT y/c", store=True, tracking=True)
    contract_file = fields.Many2many('ir.attachment',
                                     'exp_contract_contract_attachment_rel',
                                     'contract_id',
                                     'attachment_id', string="File hợp đồng cứng", required=True, store=True)
    contract_file_name = fields.Char(string="Tên file hợp đồng cứng", store=True)
    deposit_payment_file = fields.Many2many('ir.attachment',
                                            'exp_contract_deposit_attachment_rel',
                                            'contract_id',
                                            'attachment_id', string="File điện chuyển tiền cọc", store=True)
    deposit_payment_file_name = fields.Char(string="Tên file chuyển tiền cọc", store=True)

    product_file = fields.Many2many('ir.attachment',
                                    'exp_contract_product_attachment_rel',
                                    'contract_id',
                                    'attachment_id', string="File excel hàng hóa", store=True)
    export_required_date = fields.Date(string="Ngày yêu cầu xuất hàng", store=True, tracking=True)
    product_file_name = fields.Char(string="Tên file hàng hóa", store=True)
    produce_code = fields.Char(string="Mã đơn sản xuất", store=True, tracking=True)
    produce_status = fields.Selection([('draft', "Chưa sản xuất"),
                                       ('accept', "Xác nhận sản xuất"),
                                       ('done', "Đã sản xuất")],
                                      string="Trạng thái sản xuất",
                                      default='draft', store=True, tracking=True)
    product_list = fields.One2many('exp.production.order', 'contract_id', string="Chi tiết mặt hàng", store=True)

    export_detail = fields.One2many('exp.shipment', 'contract_id', string="Chi tiết xuất hàng", store=True)
    export_status = fields.Selection([('draft', "Chưa xuất hàng"),
                                      ('open', "Xuất hàng 1 phần"),
                                      ('done', "Đã hoàn tất xuất hàng")],
                                     string="Trạng thái xuất hàng",
                                     compute="_compute_export_status",
                                     default='draft', required=True, store=True, tracking=True)

    state_code = fields.Char(related='state_id.code', store=True)
    button_label = fields.Char(compute="_compute_state_button")
    date_state_change = fields.Date(string="Ngày chuyển trạng thái", store=True)

    co = fields.Boolean(string="Tạo CO", store=True)
    bh = fields.Boolean(string="Tạo BH", store=True)
    co_status = fields.Selection([('draft', "Chưa tạo CO"),
                                  ('done', "Đã tạo CO")],
                                 string="Trạng thái CO", default='draft', store=True)
    bh_status = fields.Selection([('draft', "Chưa tạo BH"),
                                  ('done', "Đã tạo BH")],
                                 string="Trạng thái BH", default='draft', store=True)
    co_file = fields.Many2many('ir.attachment',
                               'exp_contract_co_attachment_rel',
                               'contract_id',
                               'attachment_id', string="File CO", store=True)
    co_file_name = fields.Char(string="Tên file CO", store=True)
    bh_file = fields.Many2many('ir.attachment',
                               'exp_contract_bh_attachment_rel',
                               'contract_id',
                               'attachment_id', string="File BH", store=True)
    bh_file_name = fields.Char(string="Tên file BH", store=True)

    attachment_ids = fields.Many2many('ir.attachment', string='Attachments', store=True)

    follow_user = fields.Many2many('res.users', 'exp_contract_users',
                                   'exp_contract', 'res_users', string="Người theo dõi", store=True)

    bol_file = fields.Many2many('ir.attachment',
                                'exp_contract_bol_attachment_rel',
                                'contract_id',
                                'attachment_id', string="File Bill of Lading", store=True)
    bol_file_name = fields.Char(string="Tên file BoL", store=True)

    si_file = fields.Many2many('ir.attachment',
                               'exp_contract_si_attachment_rel',
                               'contract_id',
                               'attachment_id', string="File Booking", store=True)
    si_file_name = fields.Char(string="Tên file SI", store=True)

    payment_file = fields.Many2many('ir.attachment',
                                    'exp_contract_payment_attachment_rel',
                                    'contract_id',
                                    'attachment_id', string="File điện chuyển tiền thanh toán", store=True)
    payment_file_name = fields.Char(string="Tên file điện chuyển tiền thanh toán", store=True)

    declaration_file = fields.Many2many('ir.attachment',
                                        'exp_contract_declaration_attachment_rel',
                                        'contract_id',
                                        'attachment_id', string="File tờ khai", store=True)
    declaration_file_name = fields.Char(string="Tên file tờ khai", store=True)

    mtr_file = fields.Many2many('ir.attachment',
                                'exp_contract_mtr_attachment_rel',
                                'contract_id',
                                'attachment_id', string="File MTR", store=True)
    mtr_file_name = fields.Char(string="Tên file MTR", store=True)

    readonly_file_char = fields.Char(default="Tải lên tập tin của bạn.", store=True)

    expect_date = fields.Date(string="Ngày tàu chạy dự kiến", store=True)

    export_cont = fields.Integer(string="SL CONT xuất", compute="_compute_export_cont", store=True)
    export_weight = fields.Float(string="KL xuất(Tấn)", compute="_compute_export_weight", store=True)
    weight_request = fields.Float(string="KL yêu cầu(Tấn)", store=True)
    cont_left = fields.Integer(string="SL CONT còn lại", compute="cal_cont_left", store=True)
    weight_left = fields.Float(string="KL còn lại(Tấn)", compute="cal_weight_left", store=True)
    view_weight_request = fields.Char(string="KL yêu cầu", compute="_compute_weight", store=True)
    view_export_weight = fields.Char(string="KL xuất", compute="_compute_weight", store=True)
    view_weight_left = fields.Char(string="KL còn lại", compute="_compute_weight", store=True)

    @api.depends('weight_request', 'export_weight', 'weight_left')
    def _compute_weight(self):
        for r in self:
            r.view_weight_request = str(round(r.weight_request, 2)) + " tấn" if r.weight_request >= 0else ''
            r.view_export_weight = str(round(r.export_weight, 2)) + " tấn" if r.export_weight >= 0 else ''
            r.view_weight_left = str(round(r.weight_left, 2)) + " tấn" if r.weight_left >= 0 else ''

    def attach_multi(self):
        for r in self:
            vals = [(0, 0, {
                'shipment_id': rec.id,
                'invoice_number': rec.invoice_number,
                'so_cont_number': rec.so_cont_number,
                'date_shipment': str(rec.date_shipment),
                'radio_tick': False,
                'contract_id': r.id,
            }) for rec in r.export_detail]
            return {
                'name': 'Chọn SO tạo Invoice, Packing List',
                'type': 'ir.actions.act_window',
                'res_model': 'popup.invoice.pkl.choose',
                'view_mode': 'form',
                'view_id': self.env.ref(
                    'sonha_ql_xuat_khau.view_popup_invoice_pkl_choose_form'
                ).id,
                'target': 'new',
                'context': {
                    'default_contract_id': r.id,
                    'default_shipment_id': vals,
                }
            }

    @api.depends('cont_request', 'export_cont')
    def cal_cont_left(self):
        for r in self:
            cont_left = r.cont_request - r.export_cont
            r.cont_left = cont_left if cont_left >= 0 else 0

    @api.depends('weight_request', 'export_weight')
    def cal_weight_left(self):
        for r in self:
            weight_left = r.weight_request - r.export_weight
            r.weight_left = weight_left if weight_left >= 0 else 0

    @api.depends('export_detail.line_product.export_ton')
    def _compute_export_weight(self):
        for r in self:
            if r.export_detail:
                line_product = self.env['exp.product'].sudo().search([('contract_id', '=', r.id)])
                for line in line_product:
                    line.sudo().write({'cay_uom': line.cay_uom})
                total_export_ton = sum(
                    r.export_detail.mapped('line_product.export_ton')
                )
                r.export_weight = total_export_ton
            else:
                r.export_weight = 0

    @api.depends('export_detail')
    def _compute_export_cont(self):
        for r in self:
            if r.export_detail:
                r.export_cont = len(r.export_detail)
            else:
                r.export_cont = 0

    @api.depends('shipping_port_to.country_id')
    def _get_country(self):
        for r in self:
            if r.shipping_port_to.country_id:
                r.shipping_country = r.shipping_port_to.country_id.id
            else:
                r.shipping_country = None

    def check_create_access(self, user_id):
        employee_id = self.env['hr.employee'].sudo().search([('user_id', '=', user_id)])
        group_id = self.env['exp.distribute.group.user'].sudo().search([('employee_id', '=', employee_id.id)])
        for group in group_id:
            if group.group_id.create_access:
                return True
        return False

    def check_write_access(self, user_id):
        employee_id = self.env['hr.employee'].sudo().search([('user_id', '=', user_id)])
        group_id = self.env['exp.distribute.group.user'].sudo().search([('employee_id', '=', employee_id.id)])
        for group in group_id:
            if group.group_id.write_access:
                return True
        return False

    def check_unlink_access(self, user_id):
        employee_id = self.env['hr.employee'].sudo().search([('user_id', '=', user_id)])
        group_id = self.env['exp.distribute.group.user'].sudo().search([('employee_id', '=', employee_id.id)])
        for group in group_id:
            if group.group_id.unlink_access:
                return True
        return False

    def action_back_state(self):
        for r in self:
            default_state = self.env['exp.contract.state'].sudo().search([('is_default', '=', True),
                                                                          ('active', '=', True)])
            if default_state:
                r.state_id = default_state.id
            else:
                r.state_id = None

    @api.constrains('produce_code')
    def _validate_produce_code(self):
        for r in self:
            dup_record = self.sudo().search([('product_code', '=', r.produce_code),
                                             ('id', '!=', r.id)])
            if dup_record:
                raise ValidationError("Đã có hợp đồng có mã đơn sản xuất này rồi!")

    @api.constrains('contract_no')
    def _validate_produce_code(self):
        for r in self:
            dup_record = self.sudo().search([('contract_no', '=', r.contract_no),
                                             ('id', '!=', r.id)])
            if dup_record:
                raise ValidationError("Đã có hợp đồng có số hợp đồng này rồi!")

    def _read_group_state_ids(self, states, domain, order):
        return states.search([])

    def default_contract_state(self):
        default_state = self.env['exp.contract.state'].sudo().search([('is_default', '=', True),
                                                                      ('active', '=', True)])
        if default_state:
            return default_state
        else:
            return None

    @api.constrains('cont_request')
    def _validate_cont_request(self):
        for r in self:
            if r.cont_request <= 0:
                raise ValidationError("Số cont phải lớn hơn 0!")

    @api.depends('state_id')
    def _compute_state_button(self):
        for r in self:
            if r.state_id:
                state_rule = self.env['exp.state.transition.rule'].sudo().search(
                    [('from_state_id', '=', r.state_id.id)])
                if state_rule and state_rule.to_state_id.code == 'done':
                    r.button_label = False
                elif state_rule:
                    next_state = state_rule.to_state_id
                    next_state_name = state_rule.to_state_id.name
                    if next_state.code not in ['co_bh', 'bill_of_lading']:
                        next_state_name = next_state.name.lower()
                    r.button_label = f"Chuyển {next_state_name}"
                else:
                    r.button_label = False
            else:
                r.button_label = False
            if r.state_id.code == 'request':
                if r.produce_status != 'done':
                    r.button_label = False
            elif r.state_code == 'export':
                if r.export_status != 'done':
                    r.button_label = False
            elif r.state_id.code == 'co_bh':
                if (r.co_status != 'done' or not r.co_file) or (r.bh_status != 'done' or not r.bh_file):
                    r.button_label = False
            elif r.state_id.code == 'bill_of_lading':
                if not r.bol_file or not r.si_file or not r.expect_date or not r.declaration_file:
                    r.button_label = False

    def action_change_state(self):
        for r in self:
            state_rule = self.env['exp.state.transition.rule'].sudo().search([('from_state_id', '=', r.state_id.id)])
            if state_rule:
                if state_rule.required_document and r.state_id.code != 'bill_of_lading':

                    state = state_rule.to_state_id.name.lower() if state_rule.to_state_id.code not in ['co_bh', 'bill_of_lading'] else state_rule.to_state_id.name
                    name = f"Yêu cầu đính kèm file {state}"
                    if r.state_code == 'payment':
                        name = "Yêu cầu đính kèm file điện chuyển tiền thanh toán"
                    elif r.state_code == 'bill_of_lading':
                        name = 'Yêu cầu đính kèm file tờ khai'
                    return {
                        'name': name,
                        'type': 'ir.actions.act_window',
                        'res_model': 'popup.required.document',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {
                            'default_contract_id': r.id,
                            'default_state_id': state_rule.to_state_id.id,
                            'default_state_code': state_rule.to_state_id.code,
                            'default_key': 'change_stt',
                            'default_required_file': True if not r.product_file or state_rule.to_state_id.code != 'request' else False,
                        },
                    }
                if r.state_id.code == 'request':
                    if r.produce_status != 'done':
                        raise ValidationError("Đơn hàng phải được xác nhận!")
                elif r.state_id.code == 'export':
                    if r.export_status != 'done':
                        raise ValidationError("Phải thực hiện xuất hàng trước!")
                elif r.state_id.code == 'bill_of_lading':
                    if not r.bol_file or not r.si_file or not r.expect_date:
                        raise ValidationError("Cần đính kèm file Bill Of Lading, file SI và ngày tàu chạy dự kiến!")
                    attachments = (
                            r.contract_file
                            | r.declaration_file
                            | r.export_detail.mapped('file_invoice')
                            | r.export_detail.mapped('file_pkl')
                    )

                    unique = self.env['ir.attachment']
                    seen = set()

                    for att in attachments:
                        if att.checksum not in seen:
                            seen.add(att.checksum)
                            unique |= att

                    person_receive = self.env['exp.mail.config'].sudo().search([('default_rule', '=', state_rule.id)])
                    body_mail = f"""
                                        Dear anh/chị,<br/><br/>
                                        Dưới đây là các file cần thiết cảu hợp đồng {r.contract_no}.<br/><br/>
                                    """
                    sub = f"Gửi các file cần thiết tạo CO, BH của hợp đồng {r.contract_no}"
                    return {
                        'name': 'Xác nhận thông tin gửi mail',
                        'type': 'ir.actions.act_window',
                        'res_model': 'popup.config.mail.template',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {
                            'default_contract_id': r.id,
                            'default_state_code': r.state_id.code,
                            'default_attach_file': [(6, 0, unique.ids)],
                            'default_body_mail': body_mail,
                            'default_subject': sub,
                            'default_person_receive': person_receive.id if person_receive else None,
                        },
                    }
                r.state_id = state_rule.to_state_id.id
                r.date_state_change = str(datetime.now().date())
                self.env['exp.contract.state.log'].sudo().create({
                    'contract_id': r.id,
                    'from_state_id': state_rule.from_state_id.id,
                    'to_state_id': state_rule.to_state_id.id,
                    'change_by': self.env.user.id,
                })
            else:
                raise ValidationError("Không có trạng thái tiếp theo")

    @api.constrains('deposit_percent', 'deposit_amount', 'total_amount')
    def validate_required_currency(self):
        for r in self:
            if r.deposit_percent <= 0 or r.deposit_amount <= 0 or r.total_amount <= 0:
                raise ValidationError("Cần điền đầy đủ % cọc, tiền cọc, tổng tiền")

    def action_accept_produce(self):
        for r in self:
            r.produce_status = 'accept'

    def action_confirm_produce(self):
        for r in self:
            if r.produce_code:
                r.produce_status = 'done'
            else:
                raise ValidationError("Cần nhập mã đơn sản xuất!")

    def create(self, vals):
        res = super(ExpContract, self).create(vals)
        group_ids = self.env['exp.distribute.group.user'].sudo().search([]).group_id
        if group_ids:
            group_users = self.env['exp.distribute.group.user'].sudo().search([('group_id', 'in', group_ids.ids)])
            res.sudo().write({'follow_user': [(6, 0, group_users.user_id.ids)]})
        else:
            res.sudo().write({'follow_user': [(6, 0, [self.env.user.id])]})
        if self.check_create_access(self.env.user.id) or self.env.user.has_group("sonha_ql_xuat_khau.group_exp_manager") or self.env.user.has_group("sonha_ql_xuat_khau.group_exp_backup"):
            pass
        else:
            raise ValidationError("Bạn không có quyền tạo hợp đồng!")
        self.env['exp.contract.state.log'].sudo().create({
            'contract_id': res.id,
            'change_by': self.env.user.id,
            'note': "- Tạo hợp đồng mới"
        })
        return res

    def write(self, vals):
        res = super(ExpContract, self).write(vals)
        if self.check_write_access(self.env.user.id) or self.env.user.has_group(
                "sonha_ql_xuat_khau.group_exp_manager") or self.env.user.has_group(
                "sonha_ql_xuat_khau.group_exp_backup"):
            pass
        else:
            raise ValidationError("Bạn không có quyền sửa hợp đồng")
        return res

    def unlink(self):
        for r in self:
            if self.check_unlink_access(self.env.user.id) or self.env.user.has_group("sonha_ql_xuat_khau.group_exp_manager") or self.env.user.has_group("sonha_ql_xuat_khau.group_exp_backup"):
                pass
            else:
                raise ValidationError("Bạn không có quyền xóa hợp đồng")
            self.env['exp.production.order'].sudo().search([('contract_id', '=', r.id)]).unlink()
            self.env['exp.product'].sudo().search([('contract_id', '=', r.id)]).unlink()
            self.env['exp.shipment'].sudo().search([('contract_id', '=', r.id)]).unlink()
            self.env['exp.contract.state.log'].sudo().create({
                'change_by': self.env.user.id,
                'note': f"- Xóa hợp đồng {r.contract_no}"
            })
        return super(ExpContract, self).unlink()

    def _mail_track(self, tracked_fields, initial_values):
        changes, tracking_value_ids = super()._mail_track(tracked_fields, initial_values)

        if not initial_values:
            return changes, tracking_value_ids
        change_lines = []
        for command in tracking_value_ids:
            if command[0] == 0:
                values = command[2]

                field_id = values.get('field_id')
                field_name = self.env['ir.model.fields'].browse(field_id).name
                if field_name == 'state_id':
                    continue
                field_label = self._fields[field_name].string

                old_value = (
                        values.get('old_value_char')
                        or values.get('old_value_text')
                        or values.get('old_value_datetime')
                        or values.get('old_value_float')
                        or values.get('old_value_integer')
                )

                new_value = (
                        values.get('new_value_char')
                        or values.get('new_value_text')
                        or values.get('new_value_datetime')
                        or values.get('new_value_float')
                        or values.get('new_value_integer')
                )

                change_lines.append(
                    f"- {field_label}: {old_value} → {new_value}"
                )
        if change_lines:
            self.env['exp.contract.state.log'].create({
                'contract_id': self.id,
                'note': "\n".join(change_lines),
                'change_by': self.env.user.id,
            })

        return changes, tracking_value_ids

    @api.depends('export_detail.status')
    def _compute_export_status(self):
        for r in self:
            if r.export_detail:
                complete_line = r.export_detail.filtered(lambda x: x.status == 'done')
                if r.cont_request == len(complete_line) and r.cont_request == len(r.export_detail):
                    r.export_status = 'done'
                else:
                    r.export_status = 'open'
            else:
                r.export_status = 'draft'

    def action_get_sap_data(self):
        api = self.env['exp.contract.api'].sudo().search([('code', '=', 'so_data')], limit=1)
        if api:
            pr_time = datetime(2025, 1, 1, 0, 0, 0)
            api.sudo().download_data(api, self.contract_no, pr_time)
        self.fill_data_sap(self)

    def fill_data_sap(self, record):

        query = """
        DELETE FROM exp_product pr
        USING (
            SELECT
                st.so_number AS so_number
            FROM so_sap_storage st
            WHERE st.is_active = TRUE
            AND st.contract_no LIKE %s
        ) t
        WHERE pr.so_number = t.so_number;
        
        CREATE TEMP TABLE tmp_invoice_rel ON COMMIT DROP AS
        SELECT
            es.so_cont_number,
            invoice.attachment_id AS invoice,
            es.id AS old_id
        FROM exp_shipment es
        INNER JOIN exp_shipment_invoice_attachment_rel invoice
            ON es.id = invoice.contract_id
        WHERE es.contract_id = %s;
        
        CREATE TEMP TABLE tmp_pkl_rel ON COMMIT DROP AS
        SELECT
            es.so_cont_number,
            pkl.attachment_id AS pkl,
            es.id AS old_id
        FROM exp_shipment es
        INNER JOIN exp_shipment_pkl_attachment_rel pkl
            ON es.id = pkl.contract_id
        WHERE es.contract_id = %s;
        
        CREATE TEMP TABLE tmp_exp_shipment ON COMMIT DROP AS
        SELECT t.so_number AS so_number,
            s.status AS status,
            s.invoice AS invoice,
            s.packing_list AS packing_list,
            s.date_invoice AS date_invoice,
            s.date_packing_list AS date_packing_list,
            s.file_invoice_name AS file_invoice_name,
            s.file_pkl_name AS file_pkl_name
        FROM (
            SELECT st.so_number
            FROM so_sap_storage st
            WHERE st.is_active = TRUE
            AND st.contract_no LIKE %s
            GROUP BY st.so_number) t
        LEFT JOIN exp_shipment s
        ON s.so_cont_number = t.so_number;

        DELETE FROM exp_shipment es
        USING (
            SELECT
                s.so_number
            FROM so_sap_storage s
            WHERE s.is_active = TRUE
            AND s.contract_no LIKE %s
            GROUP BY s.so_number
        ) t
        WHERE es.so_cont_number = t.so_number;

        INSERT INTO exp_shipment (so_cont_number, date_shipment, invoice_number, contract_id, status, number_time, invoice, packing_list, date_invoice, date_packing_list, file_invoice_name, file_pkl_name)
        SELECT 
            t.so_number,
            t.shipment_date,
            t.contract_no,
            %s,
            COALESCE(tes.status, 'draft'),
            ROW_NUMBER() OVER (PARTITION BY %s ORDER BY t.shipment_date),
            tes.invoice,
            tes.packing_list,
            tes.date_invoice,
            tes.date_packing_list,
            tes.file_invoice_name,
            tes.file_pkl_name
        FROM (
            SELECT
                s.so_number,
                s.contract_no,
                MIN(s.shipment_date) AS shipment_date
            FROM so_sap_storage s
            WHERE s.is_active = TRUE
            AND s.contract_no LIKE %s
            GROUP BY s.so_number, s.contract_no
        ) t
        LEFT JOIN tmp_exp_shipment tes
        ON tes.so_number = t.so_number;
        
        UPDATE ir_attachment att
        SET res_id = gen.id
        FROM (
            SELECT 
                es.id,
                tmp_invoice.old_id AS old_invoice,
                tmp_pkl.old_id AS old_pkl
            FROM exp_shipment es
            LEFT JOIN tmp_invoice_rel tmp_invoice
            ON tmp_invoice.so_cont_number = es.so_cont_number
            LEFT JOIN tmp_pkl_rel tmp_pkl
            ON tmp_pkl.so_cont_number = es.so_cont_number
            GROUP BY es.id, tmp_invoice.old_id, tmp_pkl.old_id
        ) gen
        WHERE att.res_model = 'exp.shipment'
        AND (
            att.res_id = gen.old_invoice
            OR att.res_id = gen.old_pkl
        );
        
        INSERT INTO exp_shipment_invoice_attachment_rel (contract_id, attachment_id)
        SELECT
            es.id,
            tar.invoice
        FROM exp_shipment es
        INNER JOIN tmp_invoice_rel tar
            ON es.so_cont_number = tar.so_cont_number
        WHERE es.contract_id = %s;
        
        INSERT INTO exp_shipment_pkl_attachment_rel (contract_id, attachment_id)
        SELECT
            es.id,
            tar.pkl
        FROM exp_shipment es
        INNER JOIN tmp_pkl_rel tar
            ON es.so_cont_number = tar.so_cont_number
        WHERE es.contract_id = %s;

        INSERT INTO exp_product(so_id, number_order, product_code, product_name, quantity, unit, contract_id, so_number, cay_uom, ton_uom)
        SELECT
            s.id,
            ROW_NUMBER() OVER (PARTITION BY s.id ORDER BY st.shipment_date),
            st.product_code,
            st.product_name,
            st.quantity,
            st.unit,
            s.contract_id,
            s.so_cont_number,
            st.cay_uom,
            st.ton_uom
        FROM so_sap_storage st
        LEFT JOIN exp_shipment s ON st.so_number = s.so_cont_number
        WHERE st.is_active = True
        AND st.contract_no LIKE %s
        """

        self.env.cr.execute(query, (
            f"{record.contract_no}%", record.id, record.id, f"{record.contract_no}%", f"{record.contract_no}%", record.id,
            record.id, f"{record.contract_no}%", record.id, record.id,
            f"{record.contract_no}%"))
        self._compute_export_status()
        self._compute_export_cont()
        self._compute_export_weight()

    def fill_all_data_export(self):
        list_export_contract = self.env['exp.contract'].sudo().search([('state_code', '=', 'export'),
                                                                       ('export_status', '!=', 'done')])
        for r in list_export_contract:
            self.fill_data_sap(r)

    def cron_fill_data_export(self):
        self.with_delay().fill_all_data_export()

    def action_create_co(self):
        for r in self:
            return {
                'name': 'Yêu cầu đính kèm file CO',
                'type': 'ir.actions.act_window',
                'res_model': 'popup.required.document',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_contract_id': r.id,
                    'default_state_code': r.state_code,
                    'default_key': 'co_create',
                },
            }

    def action_create_bh(self):
        for r in self:
            return {
                'name': 'Yêu cầu đính kèm file BH',
                'type': 'ir.actions.act_window',
                'res_model': 'popup.required.document',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_contract_id': r.id,
                    'default_state_code': r.state_code,
                    'default_key': 'bh_create',
                },
            }

    def action_complete(self):
        for r in self:
            transition_rule = self.env['exp.state.transition.rule'].sudo()
            last_rule = transition_rule.search([('from_state_id', '=', r.state_id.id)])
            if last_rule:
                if r.mtr_file:
                    r.state_id = last_rule.to_state_id.id
                else:
                    return {
                        'name': 'Nhắc nhở đính kèm file MTR',
                        'type': 'ir.actions.act_window',
                        'res_model': 'popup.required.document',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {
                            'default_contract_id': r.id,
                            'default_state_id': last_rule.to_state_id.id,
                            'default_state_code': last_rule.to_state_id.code,
                            'default_key': 'change_stt',
                        },
                    }
            else:
                raise ValidationError("Chưa có trạng thái cuối cùng, vui lòng cài đặt thêm!")

    def mail_co_bh_reminder(self):
        co_bh_reminder = self.env['exp.co.bh.reminder'].sudo().search([('is_active', '=', True)])
        co_reminder = co_bh_reminder.filtered(lambda x: x.remind_type == 'co')
        bh_reminder = co_bh_reminder.filtered(lambda x: x.remind_type == 'bh')
        now = datetime.now().date()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        menu_id = self.env.ref('sonha_ql_xuat_khau.menu_exp_contract').id
        action_id = self.env.ref('sonha_ql_xuat_khau.action_exp_contract').id

        template = self.env.ref('sonha_ql_xuat_khau.co_bh_reminder_mail_template').sudo()
        if co_reminder:
            start_date = now - timedelta(days=bh_reminder.noti_day)
            string_date = start_date.strftime('%Y-%m-%d')
            query = """
            SELECT
                COALESCE(emp.work_email, '') AS mail_to,
                emp.name,
                ct.contract_no,
                ct.id AS contract_id
            FROM (
                SELECT 
                    created_by AS user_id,
                    contract_no,
                    id
                FROM exp_contract
                WHERE state_code = 'co_bh'
                AND date_state_change = %s
                AND co_status = 'draft'
            ) ct
            LEFT JOIN hr_employee emp
            ON ct.user_id = emp.user_id
            """

            self.env.cr.execute(query, (string_date, ))
            rows = self.env.cr.dictfetchall()
            if rows:
                for r in rows:
                    if r["mail_to"] != '':
                        template.write({
                            'email_to': r["mail_to"],
                        })
                        contract_id = r["contract_id"]
                        record_link = (
                            f"{base_url}/web#id={contract_id}"
                            f"&model=exp.contract"
                            f"&view_type=form"
                            f"&menu_id={menu_id}"
                            f"&action={action_id}"
                        )
                        template.with_context(type='CO', link=record_link).send_mail(contract_id, force_send=True)
        if bh_reminder:
            start_date = now - timedelta(days=bh_reminder.noti_day)
            string_date = start_date.strftime('%Y-%m-%d')
            query = """
            SELECT
                COALESCE(emp.work_email, '') AS mail_to,
                emp.name,
                ct.contract_no,
                ct.id AS contract_id
            FROM (
                SELECT 
                    created_by AS user_id,
                    contract_no,
                    id
                FROM exp_contract
                WHERE state_code = 'co_bh'
                AND date_state_change = %s
                AND bh_status = 'draft'
            ) ct
            LEFT JOIN hr_employee emp
            ON ct.user_id = emp.user_id
            """

            self.env.cr.execute(query, (string_date,))
            rows_bh = self.env.cr.dictfetchall()
            if rows_bh:
                for r in rows_bh:
                    if r["mail_to"] != '':
                        template.write({
                            'email_to': r["mail_to"],
                        })
                        contract_id = r["contract_id"]
                        record_link = (
                            f"{base_url}/web#id={contract_id}"
                            f"&model=exp.contract"
                            f"&view_type=form"
                            f"&menu_id={menu_id}"
                            f"&action={action_id}"
                        )
                        template.with_context(type='BH', link=record_link).send_mail(contract_id, force_send=True)

    def remind_co_bh_cron(self):
        self.with_delay().mail_co_bh_reminder()

    def action_create_bl(self):
        for r in self:
            if r.si_file:
                return {
                    'name': 'Yêu cầu đính kèm file SI',
                    'type': 'ir.actions.act_window',
                    'res_model': 'popup.required.document',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_contract_id': r.id,
                        'default_state_code': r.state_code,
                        'default_key': 'bl_create',
                    },
                }
            else:
                raise ValidationError("Cần đính kèm file SI trước!")

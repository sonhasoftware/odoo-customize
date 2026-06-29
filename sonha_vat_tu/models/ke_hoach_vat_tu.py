# -*- coding: utf-8 -*-
from datetime import date
import os as _os
import re
import base64
import io

from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Protection
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .mail_message import VAT_TU_CHATTER_SCOPES


_SQL_FUNCTIONS_PATH = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
    'data', 'sql', 'fn_ke_hoach_vat_tu.sql',
)


class KeHoachVatTu(models.Model):
    _name = 'ke.hoach.vat.tu'
    _description = 'Kỳ kế hoạch vật tư cần'
    _rec_name = 'code'
    _order = 'period_month desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(string='Số chứng từ', readonly=True, copy=False, index=True, tracking=True)
    period_month = fields.Char(
        string='Tháng bắt đầu', tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Công ty', tracking=True,
        default=lambda self: self.env.company)
    state = fields.Selection([
        ('ke_hoach', 'Kế hoạch sản xuất'),
        ('dinh_muc', 'Định mức kỳ'),
        ('tinh_toan', 'Tính toán vật tư'),
        ('tong_hop', 'Tổng hợp vật tư cần sản xuất'),
        ('dat_hang', 'Kế hoạch đặt vật tư'),
    ], default='ke_hoach', tracking=True, string='Trạng thái')
    note = fields.Text(string='Ghi chú')

    approval_company_id = fields.Many2one(
        'res.company',
        string='Đơn vị phê duyệt',
        compute='_compute_approval_company',
    )
    approval_flow_id = fields.Many2one(
        'luong.duyet',
        string='Luồng duyệt',
        copy=False,
        tracking=True,
    )
    approval_step_ids = fields.One2many(
        'buoc.duyet.ke.hoach.vat.tu',
        'period_id',
        string='Các bước duyệt',
        copy=False,
    )
    approval_state = fields.Selection(
        [
            ('draft', 'Chưa gửi duyệt'),
            ('pending', 'Đang duyệt'),
            ('approved', 'Đã duyệt'),
        ],
        string='Trạng thái phê duyệt',
        default='draft',
        required=True,
        copy=False,
        tracking=True,
    )
    approval_current_sequence = fields.Integer(
        string='Bước duyệt hiện tại',
        default=0,
        copy=False,
    )
    can_approve = fields.Boolean(compute='_compute_can_approve')

    ngay_du_phong_b4 = fields.Float(
        string='Số ngày dự phòng (B4)',
        default=15.0,
        digits=(16, 2),
        help='Dự phòng B4 = VT cần dùng tháng đầu ÷ 28 × số ngày này (mặc định 15 ≈ 2 tuần).',
        tracking=True,
    )
    ngay_du_tru_b5 = fields.Float(
        string='Số ngày dự trữ (B5)',
        default=20.0,
        digits=(16, 2),
        help='Dự trữ tối thiểu B5 = VT cần dùng tháng đầu ÷ 28 × số ngày này (mặc định 20).',
        tracking=True,
    )

    ke_hoach_kinh_doanh_ids = fields.One2many('ke.hoach.kinh.doanh', 'period_id', string='Kế hoạch kinh doanh')
    ke_hoach_san_xuat_ids = fields.One2many('ke.hoach.san.xuat', 'period_id', string='Kế hoạch sản xuất')
    ke_hoach_vat_tu_line_ids = fields.One2many('ke.hoach.vat.tu.line', 'period_id', string='Kế hoạch vật tư')
    dinh_muc_ids = fields.One2many('dinh.muc', 'period_id', string='Định mức tháng')
    tinh_toan_vat_tu_ids = fields.One2many('tinh.toan.vat.tu', 'period_id', string='Tính toán vật tư')
    tong_hop_vat_tu_ids = fields.One2many('tong.hop.vat.tu', 'period_id', string='Tổng hợp vật tư')
    kh_dat_vat_tu_ids = fields.One2many('kh.dat.vat.tu', 'period_id', string='Kế hoạch đặt vật tư')

    ke_hoach_kinh_doanh_count = fields.Integer(compute='_compute_counts')
    ke_hoach_san_xuat_count = fields.Integer(compute='_compute_counts')
    ke_hoach_vat_tu_line_count = fields.Integer(compute='_compute_counts')
    dinh_muc_count = fields.Integer(compute='_compute_counts')
    tinh_toan_vat_tu_count = fields.Integer(compute='_compute_counts')
    tong_hop_vat_tu_count = fields.Integer(compute='_compute_counts')
    kh_dat_vat_tu_count = fields.Integer(compute='_compute_counts')

    @api.depends(
        'kh_dat_vat_tu_ids.company_id',
        'ke_hoach_vat_tu_line_ids.company_id',
    )
    def _compute_approval_company(self):
        for rec in self:
            companies = rec.kh_dat_vat_tu_ids.mapped('company_id')
            if not companies:
                companies = rec.ke_hoach_vat_tu_line_ids.mapped('company_id')
            rec.approval_company_id = companies[:1] if len(companies) == 1 else False

    @api.depends(
        'approval_state',
        'approval_current_sequence',
        'approval_step_ids.sequence',
        'approval_step_ids.nguoi_duyet_id',
        'approval_step_ids.da_duyet',
    )
    def _compute_can_approve(self):
        current_user = self.env.user
        for rec in self:
            current_steps = rec.approval_step_ids.filtered(
                lambda step: (
                    step.sequence == rec.approval_current_sequence
                    and not step.da_duyet
                )
            )
            rec.can_approve = (
                rec.approval_state == 'pending'
                and any(step.nguoi_duyet_id == current_user for step in current_steps)
            )
    month_ids_preview = fields.Char(
        string='Các tháng có dữ liệu',
        compute='_compute_month_preview')

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Mã kỳ phải duy nhất!'),
        ('company_month_uniq', 'unique(company_id, period_month)', 'Công ty và tháng bắt đầu không được trùng!'),
    ]

    @api.model
    def init(self):
        with open(_SQL_FUNCTIONS_PATH, 'r', encoding='utf-8') as f:
            self.env.cr.execute(f.read())

    @api.model
    def _month_key_to_date(self, month_key):
        if not month_key:
            return False
        try:
            month, year = str(month_key).split('/')
            return date(int(year), int(month), 1)
        except Exception:
            return False

    def _get_current_production_company(self):
        user_company = self.env.company
        if user_company.company_code in ('BNH', 'SSP'):
            return user_company
        raise UserError(_(
            'Công ty mặc định của user không phải công ty sản xuất BNH/SSP. '
            'Vui lòng kiểm tra lại công ty mặc định của user trước khi thao tác kế hoạch sản xuất.'
        ))

    def _build_period_code(self, company):
        company_key = re.sub(r'[^A-Za-z0-9]+', '', company.company_code or '') or str(company.id or 'CTY')
        prefix = 'KHVT_%s_' % company_key.upper()
        latest = self.sudo().search([('code', '=like', prefix + '%')], order='code desc', limit=1)
        next_no = 1
        if latest.code:
            try:
                next_no = int(latest.code.rsplit('_', 1)[-1]) + 1
            except (TypeError, ValueError):
                next_no = 1
        return '%s%04d' % (prefix, next_no)

    @api.model
    def _get_view_cache_key(self, view_id=None, view_type='form', **options):
        key = super()._get_view_cache_key(view_id, view_type, **options)
        u = self.env.user
        return key + (
            options.get('action_id'),
            u.has_group('sonha_vat_tu.group_ban_cung_ung_vat_tu'),
            u.has_group('sonha_vat_tu.group_bo_phan_vat_tu'),
            u.has_group('sonha_vat_tu.group_truong_bo_phan_vat_tu'),
        )

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id=view_id, view_type=view_type, **options)
        if view_type not in ('tree', 'form'):
            return arch, view

        user = self.env.user
        is_ban_cung_ung = user.has_group('sonha_vat_tu.group_ban_cung_ung_vat_tu')
        action_id = options.get('action_id')
    

        action_kd = self.env.ref('sonha_vat_tu.action_ke_hoach_kinh_doanh_period', raise_if_not_found=False)
        action_sx = self.env.ref('sonha_vat_tu.action_ke_hoach_san_xuat_period', raise_if_not_found=False)
        action_vt = self.env.ref('sonha_vat_tu.action_ke_hoach_vat_tu_period', raise_if_not_found=False)

        is_kd = action_kd and action_id == action_kd.id
        is_sx = action_sx and action_id == action_sx.id
        is_vt = action_vt and action_id == action_vt.id
        if not (is_kd or is_sx or is_vt) and view_type == 'tree':
            form_ref = self.env.context.get('form_view_ref') or ''
            is_kd = 'view_ke_hoach_vat_tu_form_kd' in form_ref
            is_sx = 'view_ke_hoach_vat_tu_form_sx' in form_ref
            is_vt = 'view_ke_hoach_vat_tu_form_vt' in form_ref

        step_views = [
            self.env.ref('sonha_vat_tu.view_ke_hoach_vat_tu_form_b1', raise_if_not_found=False),
            self.env.ref('sonha_vat_tu.view_ke_hoach_vat_tu_form_vt', raise_if_not_found=False),
            self.env.ref('sonha_vat_tu.view_ke_hoach_vat_tu_form_b2', raise_if_not_found=False),
            self.env.ref('sonha_vat_tu.view_ke_hoach_vat_tu_form_b3', raise_if_not_found=False),
            self.env.ref('sonha_vat_tu.view_ke_hoach_vat_tu_form_b4', raise_if_not_found=False),
            self.env.ref('sonha_vat_tu.view_ke_hoach_vat_tu_form_b5', raise_if_not_found=False),
        ]
        is_step_form = view_type == 'form' and view_id in [v.id for v in step_views if v]

        lock_create = False
        if is_step_form and is_ban_cung_ung:
            lock_create = True
        elif is_kd and is_ban_cung_ung:
            lock_create = False
        elif is_kd or is_sx or is_vt:
            lock_create = True

        if lock_create:
            for node in arch.xpath('//tree') + arch.xpath('//form'):
                node.set('create', 'false')
        return arch, view

    @api.model_create_multi
    def create(self, vals_list):
        Company = self.env['res.company']
        counters = {}
        for vals in vals_list:
            if not vals.get('code'):
                company = Company.browse(vals.get('company_id')) if vals.get('company_id') else self.env.company
                company_id = company.id or 0
                if company_id not in counters:
                    counters[company_id] = int(self._build_period_code(company).rsplit('_', 1)[-1])
                else:
                    counters[company_id] += 1
                company_key = re.sub(r'[^A-Za-z0-9]+', '', company.company_code or '') or str(company.id or 'CTY')
                vals['code'] = 'KHVT_%s_%04d' % (company_key.upper(), counters[company_id])
        return super().create(vals_list)

    def unlink(self):
        locked = self.filtered(lambda rec: rec.state != 'ke_hoach' or rec.approval_state != 'draft')
        if locked:
            raise UserError(_(
                'Không thể xóa kỳ kế hoạch đã sang bước sau hoặc đã gửi/phê duyệt kế hoạch đặt vật tư.'
            ))
        return super().unlink()

    @api.constrains('period_month')
    def _check_period_month(self):
        pattern = re.compile(r'^(0[1-9]|1[0-2])/\d{4}$')
        for rec in self:
            if rec.period_month and not pattern.match(rec.period_month):
                raise ValidationError('Tháng bắt đầu phải đúng định dạng MM/YYYY, ví dụ 04/2026.')

    @api.constrains('ngay_du_phong_b4', 'ngay_du_tru_b5')
    def _check_tham_so_ngay(self):
        for rec in self:
            if rec.ngay_du_phong_b4 is not False and rec.ngay_du_phong_b4 <= 0:
                raise ValidationError(
                    _('Số ngày B4 phải lớn hơn 0 (đang là %s).') % rec.ngay_du_phong_b4)
            if rec.ngay_du_tru_b5 is not False and rec.ngay_du_tru_b5 <= 0:
                raise ValidationError(
                    _('Số ngày B5 phải lớn hơn 0 (đang là %s).') % rec.ngay_du_tru_b5)

    @api.depends('ke_hoach_kinh_doanh_ids', 'ke_hoach_san_xuat_ids', 'ke_hoach_vat_tu_line_ids', 'dinh_muc_ids', 'tinh_toan_vat_tu_ids',
                 'tong_hop_vat_tu_ids', 'kh_dat_vat_tu_ids')
    def _compute_counts(self):
        for rec in self:
            rec.ke_hoach_kinh_doanh_count = len(rec.ke_hoach_kinh_doanh_ids)
            rec.ke_hoach_san_xuat_count = len(rec.ke_hoach_san_xuat_ids)
            rec.ke_hoach_vat_tu_line_count = len(rec.ke_hoach_vat_tu_line_ids)
            rec.dinh_muc_count = len(rec.dinh_muc_ids)
            rec.tinh_toan_vat_tu_count = len(rec.tinh_toan_vat_tu_ids)
            rec.tong_hop_vat_tu_count = len(rec.tong_hop_vat_tu_ids)
            rec.kh_dat_vat_tu_count = len(rec.kh_dat_vat_tu_ids)

    def _get_horizon_months(self):
        self.ensure_one()
        if not self.period_month:
            return []
        try:
            m, y = map(int, self.period_month.split('/'))
            res = []
            for i in range(4):
                tm = m + i
                ty = y
                while tm > 12:
                    tm -= 12
                    ty += 1
                res.append(f"{tm:02d}/{ty}")
            return res
        except Exception:
            return []

    @api.depends('period_month')
    def _compute_month_preview(self):
        for rec in self:
            months = rec._get_horizon_months()
            rec.month_ids_preview = ', '.join(months) or False

    # ------------------------------------------------------------------
    # Actions — gọi thẳng SQL Procedure
    # ------------------------------------------------------------------

    def action_generate_b2(self):
        self.ensure_one()
        if not self.ke_hoach_vat_tu_line_ids:
            raise UserError(_(
                'Chưa có kế hoạch vật tư. Vui lòng tạo kế hoạch vật tư từ kế hoạch sản xuất trước khi sinh định mức.'
            ))
        self.env.cr.execute('CALL public.fn_sinh_dinh_muc(%s)', (self.id,))
        self.state = 'dinh_muc'
        return self.action_open_step_b2()

    def _production_company_for_auto_seed(self):
        self.ensure_one()
        production_companies = self.ke_hoach_san_xuat_ids.mapped('company_id')
        if len(production_companies) == 1:
            return production_companies
        if self.env.company.company_code in ('BNH', 'SSP'):
            return self.env.company
        return self.env['res.company'].browse()

    def _sync_production_from_business(self):
        self.ensure_one()
        if not self.ke_hoach_kinh_doanh_ids:
            return
        Production = self.env['ke.hoach.san.xuat'].sudo()
        company = self._production_company_for_auto_seed()
        existing = {
            line.ma_sap
            for line in self.ke_hoach_san_xuat_ids
        }
        vals_list = []
        for line in self.ke_hoach_kinh_doanh_ids:
            if line.ma_sap in existing:
                continue
            vals_list.append({
                'period_id': self.id,
                'company_id': company.id or False,
                'nganh_hang': line.nganh_hang,
                'ma_hang': line.ma_hang,
                'ma_sap': line.ma_sap,
                'qty_t0': line.qty_t0,
                'qty_t1': line.qty_t1,
                'qty_t2': line.qty_t2,
                'qty_t3': line.qty_t3,
                'note': line.note,
            })
        if vals_list:
            Production.with_context(
                is_importing=True,
                allow_unassigned_production_company=True,
            ).create(vals_list)

    def _prepare_material_plan_values_from_production(self, production_company):
        self.ensure_one()
        business_by_key = {
            line.ma_sap: line
            for line in self.ke_hoach_kinh_doanh_ids
        }
        production_keys = {
            line.ma_sap
            for line in self.ke_hoach_san_xuat_ids
        }
        missing = sorted(set(business_by_key) - production_keys)
        if missing:
            messages = []
            for key in missing[:20]:
                messages.append('Mã SAP=%s' % (key or ''))
            if len(missing) > 20:
                messages.append('... còn %s dòng khác' % (len(missing) - 20))
            raise UserError(_(
                'Kế hoạch sản xuất đang thiếu dòng so với kế hoạch kinh doanh:\n%s\n'
                'Nếu không sản xuất, vui lòng giữ dòng và nhập Số lượng = 0.'
            ) % '\n'.join(messages))

        vals_list = []
        for line in self.ke_hoach_san_xuat_ids:
            ma_sap = line.ma_sap
            business_line = business_by_key.get(ma_sap)
            vals_list.append({
                'period_id': self.id,
                'company_id': production_company.id,
                'nganh_hang': line.nganh_hang,
                'ma_hang': line.ma_hang,
                'ma_sap': line.ma_sap,
                'qty_kd_t0': business_line.qty_t0 if business_line else 0.0,
                'qty_kd_t1': business_line.qty_t1 if business_line else 0.0,
                'qty_kd_t2': business_line.qty_t2 if business_line else 0.0,
                'qty_kd_t3': business_line.qty_t3 if business_line else 0.0,
                'qty_sx_t0': line.qty_t0,
                'qty_sx_t1': line.qty_t1,
                'qty_sx_t2': line.qty_t2,
                'qty_sx_t3': line.qty_t3,
                'qty_t0': line.qty_t0,
                'qty_t1': line.qty_t1,
                'qty_t2': line.qty_t2,
                'qty_t3': line.qty_t3,
                'note': line.note,
            })
        return vals_list

    def action_create_material_plan(self):
        self.ensure_one()
        if self.state != 'ke_hoach':
            raise UserError(_('Kế hoạch đã sang bước sau, không thể tạo lại kế hoạch vật tư.'))
        if not self.ke_hoach_san_xuat_ids:
            raise UserError(_('Chưa có kế hoạch sản xuất để tạo kế hoạch vật tư.'))
        if self.ke_hoach_vat_tu_line_ids:
            raise UserError(_('Kế hoạch vật tư đã có dữ liệu. Vui lòng xóa dữ liệu cũ nếu cần tạo lại.'))

        production_company = self._get_current_production_company()
        other_company_lines = self.ke_hoach_san_xuat_ids.filtered(
            lambda line: line.company_id and line.company_id != production_company
        )
        if other_company_lines:
            other_codes = ', '.join(sorted(set(
                other_company_lines.mapped('company_id.company_code')
            )))
            raise UserError(_(
                'Kế hoạch sản xuất đã thuộc đơn vị %s, trong khi công ty hiện tại của bạn là %s. '
                'Vui lòng chuyển đúng công ty trước khi tạo kế hoạch vật tư.'
            ) % (other_codes, production_company.company_code))

        unassigned_lines = self.ke_hoach_san_xuat_ids.filtered(lambda line: not line.company_id)
        if unassigned_lines:
            unassigned_lines.with_context(
                is_importing=True,
                allow_unassigned_production_company=True,
            ).write({'company_id': production_company.id})

        vals_list = self._prepare_material_plan_values_from_production(production_company)
        if vals_list:
            self.env['ke.hoach.vat.tu.line'].sudo().with_context(skip_period_lock=True).create(vals_list)
        self.with_context(vat_tu_chatter_scope='vt').message_post(
            body=_(
                'Đã tạo %s dòng kế hoạch vật tư theo đơn vị sản xuất %s.'
            ) % (len(vals_list), production_company.company_code)
        )
        return self.action_open_workflow_vt()

    def action_compute_b3(self):
        self.ensure_one()
        self.env.cr.execute('CALL public.fn_tinh_toan_vat_tu(%s)', (self.id,))
        self.state = 'tinh_toan'
        return self.action_open_step_b3()

    def action_compute_b4(self):
        self.ensure_one()
        self.env.cr.execute(
            'CALL public.fn_tong_hop_vat_tu(%s, %s)',
            (self.id, self.ngay_du_phong_b4 or 15.0)
        )
        self.state = 'tong_hop'
        return self.action_open_step_b4()

    def action_compute_b5(self):
        self.ensure_one()
        self.env.cr.execute(
            'CALL public.fn_ke_hoach_dat_vat_tu(%s, %s)',
            (self.id, self.ngay_du_tru_b5 or 20.0)
        )
        self.state = 'dat_hang'
        return self.action_open_step_b5()

    def _approval_manager_user(self):
        self.ensure_one()
        return self.env.user

    def action_submit_approval(self):
        self.ensure_one()
        if self.state != 'dat_hang' or not self.kh_dat_vat_tu_ids:
            raise UserError(_('Chỉ có thể gửi duyệt sau khi đã sinh kế hoạch đặt vật tư.'))
        if self.approval_state != 'draft':
            raise UserError(_('Kế hoạch này đã được gửi duyệt.'))
        if not self.approval_flow_id:
            raise UserError(_('Vui lòng chọn Luồng duyệt trước khi gửi duyệt.'))
        if self.approval_flow_id.model_id.model != self._name:
            raise UserError(_(
                'Luồng duyệt đã chọn không áp dụng cho model Kế hoạch vật tư.'
            ))
        if not self.approval_company_id:
            raise UserError(_(
                'Không xác định được duy nhất một đơn vị sản xuất để phê duyệt.'
            ))
        if self.approval_flow_id.dvcs != self.approval_company_id:
            raise UserError(_(
                'Luồng duyệt thuộc đơn vị %s, nhưng kế hoạch đặt vật tư thuộc đơn vị %s.'
            ) % (
                self.approval_flow_id.dvcs.company_code or self.approval_flow_id.dvcs.name,
                self.approval_company_id.company_code or self.approval_company_id.name,
            ))

        configured_steps = self.approval_flow_id.sudo().step_ids.sorted(
            key=lambda step: (step.sequence, step.id)
        )
        if not configured_steps:
            raise UserError(_('Luồng duyệt chưa có bước duyệt nào.'))

        step_values = []
        for configured_step in configured_steps:
            if configured_step.phuong_thuc == 'ql':
                approvers = self._approval_manager_user()
            else:
                approvers = configured_step.ten_nguoi_duyet
            if not approvers:
                raise UserError(_(
                    'Bước duyệt STT %s chưa xác định được người duyệt.'
                ) % configured_step.sequence)
            for approver in approvers:
                step_values.append({
                    'period_id': self.id,
                    'sequence': configured_step.sequence,
                    'phuong_thuc': configured_step.phuong_thuc,
                    'vai_tro_id': configured_step.vai_tro.id or False,
                    'nguoi_duyet_id': approver.id,
                })

        self.approval_step_ids.sudo().unlink()
        self.env['buoc.duyet.ke.hoach.vat.tu'].sudo().create(step_values)
        first_sequence = min(value['sequence'] for value in step_values)
        self.write({
            'approval_state': 'pending',
            'approval_current_sequence': first_sequence,
        })
        self.message_post(body=_(
            '%s đã gửi duyệt kế hoạch đặt vật tư theo luồng "%s".'
        ) % (self.env.user.name, self.approval_flow_id.ten))
        self.invalidate_recordset([
            'approval_step_ids',
            'approval_state',
            'approval_current_sequence',
        ])
        return self.action_approve_material_plan()

    def action_approve_material_plan(self):
        self.ensure_one()
        if self.approval_state != 'pending':
            raise UserError(_('Kế hoạch không ở trạng thái đang duyệt.'))

        current_steps = self.approval_step_ids.filtered(
            lambda step: step.sequence == self.approval_current_sequence
        )
        my_steps = current_steps.filtered(
            lambda step: step.nguoi_duyet_id == self.env.user and not step.da_duyet
        )
        if not my_steps:
            raise UserError(_('Chưa đến lượt bạn duyệt kế hoạch này.'))

        my_steps.sudo().write({
            'da_duyet': True,
            'ngay_duyet': self.env.cr.now(),
        })
        self.message_post(body=_(
            '%s đã duyệt bước %s.'
        ) % (self.env.user.name, self.approval_current_sequence))

        if all(current_steps.mapped('da_duyet')):
            next_sequences = self.approval_step_ids.filtered(
                lambda step: step.sequence > self.approval_current_sequence
            ).mapped('sequence')
            if next_sequences:
                self.approval_current_sequence = min(next_sequences)
            else:
                self.write({
                    'approval_state': 'approved',
                    'approval_current_sequence': 0,
                })
                self.message_post(body=_('Kế hoạch đặt vật tư đã được phê duyệt hoàn tất.'))
        return self.action_open_step_b5()

    def action_reset_to_draft(self):
        for period in self:
            period.with_context(vat_tu_chatter_scope='vt').message_post(
                body=_('%s đã reset về nháp.') % self.env.user.name
            )
            period.sudo().approval_step_ids.unlink()
            period.sudo().dinh_muc_ids.unlink()
            period.sudo().tinh_toan_vat_tu_ids.unlink()
            period.sudo().tong_hop_vat_tu_ids.unlink()
            period.sudo().kh_dat_vat_tu_ids.unlink()
            period.write({
                'state': 'ke_hoach',
                'approval_flow_id': False,
                'approval_state': 'draft',
                'approval_current_sequence': 0,
            })

    def _apply_plan_excel_style(self, ws, header_row, max_col):
        base_font = Font(name='Times New Roman', size=10)
        label_font = Font(name='Times New Roman', size=10, bold=True)
        value_font = Font(name='Times New Roman', size=10)
        header_font = Font(name='Times New Roman', size=10, bold=True, color='FFFFFF')
        header_fill = PatternFill(fill_type='solid', fgColor='3F6F8F')
        thin_side = Side(style='thin', color='B7C6D0')
        header_side = Side(style='thin', color='2F556D')
        meta_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
        header_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
        header_border = Border(left=header_side, right=header_side, top=header_side, bottom=header_side)
        header_alignment = Alignment(horizontal='center', vertical='center')
        body_alignment = Alignment(vertical='center')

        for row in ws.iter_rows(min_row=1, max_row=max(ws.max_row, header_row), min_col=1, max_col=max_col):
            for cell in row:
                cell.font = base_font
                cell.alignment = body_alignment

        for row_idx in (1, 2, 3):
            label_cell = ws.cell(row=row_idx, column=1)
            value_cell = ws.cell(row=row_idx, column=2)
            label_cell.font = label_font
            value_cell.font = value_font
            label_cell.border = meta_border
            label_cell.alignment = Alignment(horizontal='left', vertical='center')
            value_cell.alignment = Alignment(horizontal='left', vertical='center')
            for col_idx in range(2, max_col + 1):
                meta_cell = ws.cell(row=row_idx, column=col_idx)
                meta_cell.border = meta_border
                meta_cell.font = value_font
                meta_cell.alignment = Alignment(horizontal='left', vertical='center')

        for cell in ws[header_row][:max_col]:
            cell.font = header_font
            cell.fill = header_fill
            cell.border = header_border
            cell.alignment = header_alignment

        ws.row_dimensions[header_row].height = 22
        ws.freeze_panes = ws.cell(row=header_row + 1, column=1).coordinate

    def _write_plan_metadata(self, ws):
        ws.merge_cells(start_row=1, start_column=2, end_row=1, end_column=5)
        ws.merge_cells(start_row=2, start_column=2, end_row=2, end_column=5)
        ws.merge_cells(start_row=3, start_column=2, end_row=3, end_column=5)
        ws.cell(row=1, column=1, value='Mã')
        ws.cell(row=1, column=2, value=self.code or '')
        ws.cell(row=2, column=1, value='Tháng bắt đầu')
        ws.cell(row=2, column=2, value=self.period_month or '')
        ws.cell(row=3, column=1, value='Công ty')
        ws.cell(row=3, column=2, value=self.company_id.name or '')

    def _protect_plan_sheet(self, ws, header_row, unlocked_cols):
        for row in ws.iter_rows(min_row=1, max_row=max(ws.max_row, header_row + 100), min_col=1, max_col=ws.max_column):
            for cell in row:
                cell.protection = Protection(locked=True)
        for row_idx in range(header_row + 1, max(ws.max_row, header_row + 100) + 1):
            for col_idx in unlocked_cols:
                ws.cell(row=row_idx, column=col_idx).protection = Protection(locked=False)
        ws.protection.sheet = True

    def _xlsx_download_action(self, wb, filename):
        output = io.BytesIO()
        wb.save(output)
        attachment = self.env['ir.attachment'].sudo().create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(output.getvalue()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

    def action_download_b1_template(self):
        self.ensure_one()
        if self.state != 'ke_hoach':
            raise UserError(_('Kế hoạch đã sang bước sau, không thể tải template để import lại.'))
        if not (
            self.env.user.has_group('sonha_vat_tu.group_ban_cung_ung_vat_tu') or
            self.env.user.has_group('sonha_vat_tu.group_truong_bo_phan_vat_tu')
        ):
            raise UserError(_('Bạn không có quyền tải template kế hoạch kinh doanh.'))

        wb = Workbook()
        ws = wb.active
        ws.title = 'Ke hoach kinh doanh'
        self._write_plan_metadata(ws)
        months = self._get_horizon_months()
        headers = ['Ngành hàng', 'Tên hàng', 'Mã hàng', 'Mã SAP']
        headers += ['Tháng %s' % m for m in months]
        header_row = 6
        for col_idx, label in enumerate(headers, start=1):
            ws.cell(row=header_row, column=col_idx, value=label)
        self._apply_plan_excel_style(ws, header_row, len(headers))
        ws.column_dimensions['A'].width = 18
        ws.column_dimensions['B'].width = 22
        ws.column_dimensions['C'].width = 24
        ws.column_dimensions['D'].width = 24
        ws.column_dimensions['E'].width = 16
        ws.column_dimensions['F'].width = 16
        ws.column_dimensions['G'].width = 16
        ws.column_dimensions['H'].width = 16
        return self._xlsx_download_action(
            wb,
            'KHKD_%s.xlsx' % (self.code),
        )

    def action_open_import_kinh_doanh_wizard(self):
        self.ensure_one()
        if self.state != 'ke_hoach':
            raise UserError(_('Kế hoạch kinh doanh đã khóa vì kỳ kế hoạch đã sang bước sau.'))
        if not (
            self.env.user.has_group('sonha_vat_tu.group_ban_cung_ung_vat_tu') or
            self.env.user.has_group('sonha_vat_tu.group_truong_bo_phan_vat_tu')
        ):
            raise UserError(_('Bạn không có quyền import kế hoạch kinh doanh.'))
        return {
            'name': _('Import kế hoạch kinh doanh'),
            'type': 'ir.actions.act_window',
            'res_model': 'import.ke.hoach.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_period_id': self.id,
                'default_import_type': 'business',
            },
        }

    def action_open_import_san_xuat_wizard(self):
        self.ensure_one()
        if self.state != 'ke_hoach':
            raise UserError(_('Kế hoạch sản xuất đã khóa vì kỳ kế hoạch đã sang bước sau.'))
        if not (
            self.env.user.has_group('sonha_vat_tu.group_bo_phan_vat_tu') or
            self.env.user.has_group('sonha_vat_tu.group_truong_bo_phan_vat_tu')
        ):
            raise UserError(_('Bạn không có quyền import kế hoạch sản xuất.'))
        return {
            'name': _('Import kế hoạch sản xuất'),
            'type': 'ir.actions.act_window',
            'res_model': 'import.ke.hoach.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_period_id': self.id,
                'default_import_type': 'production',
            },
        }

    def action_open_import_wizard(self):
        return self.action_open_import_kinh_doanh_wizard()

    def action_export_san_xuat(self):
        self.ensure_one()
        if self.state != 'ke_hoach':
            raise UserError(_('Kế hoạch đã sang bước sau, không thể export lại cho sản xuất.'))
        if not (
            self.env.user.has_group('sonha_vat_tu.group_bo_phan_vat_tu') or
            self.env.user.has_group('sonha_vat_tu.group_truong_bo_phan_vat_tu')
        ):
            raise UserError(_('Bạn không có quyền export kế hoạch cho sản xuất.'))
        lines = self.ke_hoach_san_xuat_ids.sorted(lambda r: (
            r.nganh_hang or '',
            r.ten_hang or '',
            r.ma_hang or '',
            r.ma_sap or '',
        ))
        if not lines:
            raise UserError(_('Chưa có kế hoạch sản xuất để export.'))

        months = self._get_horizon_months()

        wb = Workbook()
        ws = wb.active
        ws.title = 'Ke hoach san xuat'
        self._write_plan_metadata(ws)
        headers = ['Ngành hàng', 'Tên hàng', 'Mã hàng', 'Mã SAP']
        headers += ['Tháng %s' % month for month in months]
        header_row = 6
        for col_idx, label in enumerate(headers, start=1):
            ws.cell(row=header_row, column=col_idx, value=label)

        for line in lines:
            ws.append([
                line.nganh_hang or '',
                line.ten_hang or '',
                line.ma_hang or '',
                line.ma_sap or '',
                line.qty_t0 or 0.0,
                line.qty_t1 or 0.0,
                line.qty_t2 or 0.0,
                line.qty_t3 or 0.0,
            ])

        self._apply_plan_excel_style(ws, header_row, len(headers))

        month_col_indexes = [5, 6, 7, 8]
        self._protect_plan_sheet(ws, header_row, month_col_indexes)

        for col_idx in range(1, len(headers) + 1):
            max_len = max(len(str(ws.cell(row=row_idx, column=col_idx).value or '')) for row_idx in range(1, ws.max_row + 1))
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max(max_len + 2, 12), 28)
        ws.column_dimensions['A'].width = 22
        ws.column_dimensions['B'].width = 22
        ws.column_dimensions['C'].width = 24
        ws.column_dimensions['D'].width = 24

        return self._xlsx_download_action(
            wb,
            'KHSX_%s.xlsx' % (self.code or self.id),
        )

    def _action_open_step(self, view_xmlid):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Kế hoạch vật tư'),
            'res_model': 'ke.hoach.vat.tu',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref(view_xmlid).sudo().id, 'form')],
            'target': 'current',
        }

    def action_open_workflow_sx(self):
        return self._action_open_step('sonha_vat_tu.view_ke_hoach_vat_tu_form_sx')

    def action_open_workflow_vt(self):
        return self._action_open_step('sonha_vat_tu.view_ke_hoach_vat_tu_form_vt')

    def action_open_step_b1(self):
        return self._action_open_step('sonha_vat_tu.view_ke_hoach_vat_tu_form_vt')

    def action_open_step_b2(self):
        return self._action_open_step('sonha_vat_tu.view_ke_hoach_vat_tu_form_b2')

    def action_open_step_b3(self):
        return self._action_open_step('sonha_vat_tu.view_ke_hoach_vat_tu_form_b3')

    def action_open_step_b4(self):
        return self._action_open_step('sonha_vat_tu.view_ke_hoach_vat_tu_form_b4')

    def action_open_step_b5(self):
        return self._action_open_step('sonha_vat_tu.view_ke_hoach_vat_tu_form_b5')

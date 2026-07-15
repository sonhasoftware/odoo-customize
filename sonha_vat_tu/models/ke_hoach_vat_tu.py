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
from openpyxl.worksheet.datavalidation import DataValidation
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
    company_id = fields.Many2one(
        'res.company', string='Đơn vị lập kế hoạch',
        index=True, readonly=True, copy=False,
        default=lambda self: self.env.company.id,
        help='Đơn vị của user tạo kỳ; chỉ dùng phân quyền, không hiển thị trên form.',
    )
    period_month = fields.Char(
        string='Tháng bắt đầu', tracking=True)
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
    workflow_form_view_id = fields.Many2one(
        'ir.ui.view',
        string='Form view workflow',
        copy=False,
        index=True,
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
    tong_hop_vat_tu_ids = fields.One2many(
        'tong.hop.vat.tu', 'period_id', string='Tổng hợp vật tư',
        domain=[('don_vi_kd_id', '=', False)],
    )
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
        (
            'period_company_month_uniq',
            'unique(company_id, period_month)',
            'Tháng bắt đầu không được trùng trong cùng đơn vị lập kế hoạch!',
        ),
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

    @api.model
    def _get_creator_company_code(self):
        company = self.env.company
        code = (getattr(company, 'company_code', None) or '').strip()
        return code or (company.name or 'XX').strip()

    @api.model
    def _period_code_prefix(self, company_code=None):
        code = (company_code or self._get_creator_company_code()).strip()
        return 'KHVT_%s' % code if code else 'KHVT'

    @api.model
    def _next_period_code(self, company_code=None):
        prefix = self._period_code_prefix(company_code) + '_'
        latest = self.sudo().search([('code', '=like', prefix + '%')], order='code desc', limit=1)
        next_no = 1
        if latest.code:
            try:
                next_no = int(latest.code.rsplit('_', 1)[-1]) + 1
            except (TypeError, ValueError):
                next_no = 1
        return '%s%03d' % (prefix, next_no)

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
        for vals in vals_list:
            if not vals.get('company_id'):
                vals['company_id'] = self.env.company.id
            if not vals.get('code'):
                vals['code'] = self._next_period_code()
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
            rec.tong_hop_vat_tu_count = len(rec.tong_hop_vat_tu_ids.filtered(lambda r: not r.don_vi_kd_id))
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
        production_companies = self.ke_hoach_san_xuat_ids.mapped('company_id').filtered(lambda c: c)
        if len(production_companies) == 1:
            return production_companies
        if self.env.company.company_code in ('BNH', 'SSP'):
            return self.env.company
        return self.env['res.company'].browse()

    @api.model
    def _aggregate_kd_by_sap(self, kd_lines):
        """Gom số lượng KD theo ma_sap (nhiều đơn vị cùng SAP → cộng qty)."""
        agg = {}
        for line in kd_lines.filtered('ma_sap'):
            bucket = agg.setdefault(line.ma_sap, {
                'line': line,
                'qty_t0': 0.0,
                'qty_t1': 0.0,
                'qty_t2': 0.0,
                'qty_t3': 0.0,
            })
            bucket['qty_t0'] += line.qty_t0 or 0.0
            bucket['qty_t1'] += line.qty_t1 or 0.0
            bucket['qty_t2'] += line.qty_t2 or 0.0
            bucket['qty_t3'] += line.qty_t3 or 0.0
        return agg

    def _sync_production_from_business(self):
        """Đồng bộ ke.hoach.san.xuat theo ke.hoach.kinh.doanh (tạo/sửa/xóa)."""
        self.ensure_one()
        if self.state != 'ke_hoach':
            return

        Production = self.env['ke.hoach.san.xuat'].sudo()
        sync_ctx = {
            'is_importing': True,
            'allow_unassigned_production_company': True,
            'skip_kd_sx_sync': True,
        }
        company = self._production_company_for_auto_seed()

        business_by_sap = self._aggregate_kd_by_sap(self.ke_hoach_kinh_doanh_ids)

        existing_sx = self.ke_hoach_san_xuat_ids
        sx_by_sap = {}
        for line in existing_sx:
            sx_by_sap.setdefault(line.ma_sap, line)

        to_delete = existing_sx.filtered(lambda line: line.ma_sap not in business_by_sap)
        if to_delete:
            to_delete.with_context(**sync_ctx).unlink()

        qty_fields = ('qty_t0', 'qty_t1', 'qty_t2', 'qty_t3')
        to_create_sx = []
        to_update_sx = []
        for ma_sap, bucket in business_by_sap.items():
            kd_line = bucket['line']
            vals = {
                'ma_hang': kd_line.ma_hang,
                'ma_sap': ma_sap,
                'qty_t0': bucket['qty_t0'],
                'qty_t1': bucket['qty_t1'],
                'qty_t2': bucket['qty_t2'],
                'qty_t3': bucket['qty_t3'],
                'note': kd_line.note,
            }
            sx_line = sx_by_sap.get(ma_sap)
            if sx_line:
                if any((sx_line[f] or 0.0) != (vals[f] or 0.0) for f in qty_fields) or (
                    (sx_line.ma_hang or '') != (vals['ma_hang'] or '')
                    or (sx_line.note or '') != (vals['note'] or '')
                ):
                    to_update_sx.append((sx_line.id, vals))
            else:
                to_create_sx.append({
                    **vals,
                    'period_id': self.id,
                    'company_id': company.id or False,
                })

        if to_create_sx:
            Production.with_context(**sync_ctx).create(to_create_sx)
        if to_update_sx:
            Production._sql_bulk_import_update(to_update_sx)

    def _prepare_material_plan_values_from_production(self, production_company):
        self.ensure_one()
        business_by_key = self._aggregate_kd_by_sap(self.ke_hoach_kinh_doanh_ids)
        production_keys = {
            line.ma_sap
            for line in self.ke_hoach_san_xuat_ids
        }
        missing = sorted(set(business_by_key) - production_keys)
        if missing:
            messages = []
            for key in missing[:20]:
                messages.append('Mã=%s' % (key or ''))
            if len(missing) > 20:
                messages.append('... còn %s dòng khác' % (len(missing) - 20))
            raise UserError(_(
                'Kế hoạch sản xuất đang thiếu dòng so với kế hoạch kinh doanh:\n%s\n'
                'Nếu không sản xuất, vui lòng giữ dòng và nhập Số lượng = 0.'
            ) % '\n'.join(messages))

        sx_lines = self.ke_hoach_san_xuat_ids
        sap_codes = sorted({(line.ma_sap or '').strip() for line in sx_lines if (line.ma_sap or '').strip()})
        meta_map = self.env['ma.hang'].get_mdm_sap_meta_map(sap_codes) if sap_codes else {}
        NganhHang = self.env['mdm.nganh.hang'].sudo()
        nganh_names = {}
        nh_ids = {m['nganh_hang_id'] for m in meta_map.values() if m.get('nganh_hang_id')}
        if nh_ids:
            for nh in NganhHang.browse(list(nh_ids)):
                nganh_names[nh.id] = nh.ten or ''

        vals_list = []
        for line in sx_lines:
            ma_sap = line.ma_sap
            kd_bucket = business_by_key.get(ma_sap)
            meta = meta_map.get((ma_sap or '').strip(), {})
            nganh_hang = line.nganh_hang.ten if line.nganh_hang else ''
            if not nganh_hang and meta.get('nganh_hang_id'):
                nganh_hang = nganh_names.get(meta['nganh_hang_id'], '')
            vals_list.append({
                'period_id': self.id,
                'company_id': production_company.id,
                'nganh_hang': nganh_hang,
                'ma_hang': line.ma_hang,
                'ma_sap': line.ma_sap,
                'qty_kd_t0': kd_bucket['qty_t0'] if kd_bucket else 0.0,
                'qty_kd_t1': kd_bucket['qty_t1'] if kd_bucket else 0.0,
                'qty_kd_t2': kd_bucket['qty_t2'] if kd_bucket else 0.0,
                'qty_kd_t3': kd_bucket['qty_t3'] if kd_bucket else 0.0,
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
        Line = self.env['ke.hoach.vat.tu.line'].sudo()
        import_ctx = {'skip_period_lock': True, 'is_importing': True, 'tracking_disable': True}
        DuLieu = self.env['du.lieu.tong.hop.vat.tu'].sudo()

        def _create_lines():
            if vals_list:
                Line.with_context(**import_ctx).create(vals_list)
            return len(vals_list)

        count = DuLieu.run_period_bulk(self.id, ['b1'], _create_lines)
        self.with_context(vat_tu_chatter_scope='vt').message_post(
            body=_(
                'Đã tạo %s dòng kế hoạch vật tư theo đơn vị sản xuất %s.'
            ) % (count, production_company.company_code)
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

    def action_open_import_bcu_wizard(self):
        self.ensure_one()
        if self.state != 'tong_hop':
            raise UserError(_('Chỉ import hàng đi đường BCU khi đã ở bước Tổng hợp vật tư cần sản xuất.'))
        if not self.tong_hop_vat_tu_ids.filtered(lambda r: not r.don_vi_kd_id):
            raise UserError(_('Chưa có dữ liệu Tổng hợp vật tư cần sản xuất. Vui lòng chạy bước này trước khi import.'))
        view = self.env.ref('sonha_vat_tu.view_import_tong_hop_bcu_wizard_form')
        return {
            'name': _('Import hàng đi đường BCU'),
            'type': 'ir.actions.act_window',
            'res_model': 'import.tong.hop.bcu.wizard',
            'view_mode': 'form',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': {'default_period_id': self.id},
        }

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

    def _get_plan_company_codes(self):
        return sorted({
            (c.company_code or '').strip()
            for c in self.env['res.company'].sudo().search([])
            if (c.company_code or '').strip()
        })

    def _apply_plan_company_code_validation(self, wb, ws, header_row, company_codes):
        if not company_codes:
            return
        ref_sheet = wb.create_sheet('_company_codes')
        ref_sheet.sheet_state = 'hidden'
        for row_idx, code in enumerate(company_codes, start=1):
            ref_sheet.cell(row=row_idx, column=1, value=code)
        dv = DataValidation(
            type='list',
            formula1=f"='_company_codes'!$A$1:$A${len(company_codes)}",
            allow_blank=False,
        )
        dv.error = _('Chỉ được chọn mã đơn vị có trong danh mục.')
        dv.errorTitle = _('Đơn vị không hợp lệ')
        ws.add_data_validation(dv)
        first_data_row = header_row + 1
        dv.add(f'A{first_data_row}:A5000')

    def _write_plan_metadata(self, ws):
        ws.merge_cells(start_row=1, start_column=2, end_row=1, end_column=5)
        ws.merge_cells(start_row=2, start_column=2, end_row=2, end_column=5)
        ws.cell(row=1, column=1, value='Mã')
        ws.cell(row=1, column=2, value=self.code or '')
        ws.cell(row=2, column=1, value='Tháng bắt đầu')
        ws.cell(row=2, column=2, value=self.period_month or '')

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
        headers = ['Đơn vị', 'Ngành hàng', 'Tên hàng', 'Mã hàng', 'Mã']
        headers += ['Tháng %s' % m for m in months]
        header_row = 6
        for col_idx, label in enumerate(headers, start=1):
            ws.cell(row=header_row, column=col_idx, value=label)
        self._apply_plan_excel_style(ws, header_row, len(headers))
        self._apply_plan_company_code_validation(
            wb, ws, header_row, self._get_plan_company_codes())
        ws.column_dimensions['A'].width = 12
        ws.column_dimensions['B'].width = 18
        ws.column_dimensions['C'].width = 22
        ws.column_dimensions['D'].width = 24
        ws.column_dimensions['E'].width = 24
        ws.column_dimensions['F'].width = 16
        ws.column_dimensions['G'].width = 16
        ws.column_dimensions['H'].width = 16
        ws.column_dimensions['I'].width = 16
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
            r.nganh_hang.ten if r.nganh_hang else '',
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
        headers = ['Ngành hàng', 'Tên hàng', 'Mã hàng', 'Mã']
        headers += ['Tháng %s' % month for month in months]
        header_row = 6
        for col_idx, label in enumerate(headers, start=1):
            ws.cell(row=header_row, column=col_idx, value=label)

        for line in lines:
            ws.append([
                line.nganh_hang.ten if line.nganh_hang else '',
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

    def action_export_kh_dat_vat_tu(self):
        """Xuất Excel bước 5."""
        self.ensure_one()
        if self.state != 'dat_hang':
            raise UserError(_('Chỉ export được ở bước Kế hoạch đặt vật tư.'))
        lines = self.kh_dat_vat_tu_ids.sorted(
            key=lambda r: ((r.ma_sap or '').strip(), r.id),
        )
        if not lines:
            raise UserError(_('Chưa có dữ liệu kế hoạch đặt vật tư để xuất.'))

        months = self._get_horizon_months()
        if len(months) < 4:
            months = (months + [''] * 4)[:4]

        wb = Workbook()
        ws = wb.active
        ws.title = 'Ke hoach dat vat tu'

        ws.cell(row=1, column=1, value='Số chứng từ')
        ws.cell(row=1, column=2, value=self.code or '')
        ws.cell(row=2, column=1, value='Tháng bắt đầu')
        ws.cell(row=2, column=2, value=self.period_month or '')

        header_row1 = 4
        header_row2 = 5
        data_row = 6

        fixed_start = [
            ('Mã NVL', 'ma_sap', 'text'),
            ('Tên NVL', 'ten_nvl', 'text'),
            ('Chủng loại', 'chung_loai', 'text'),
            ('ĐVT', 'don_vi_tinh', 'dvt'),
            ('Đơn giá tồn kho', 'don_gia_ton_kho', 'money'),
            ('Tồn NVL đầu kỳ', 'tong_ton_nvl_sl', 'qty'),
            ('Giá trị tồn NVL', 'gia_tri_ton_nvl_dau_ky', 'money'),
        ]
        month_groups = [
            ('Cần dùng', 'tong_sl_vt_can_dung_t', 'Tổng cần dùng', 'tong_vt_can_dung'),
            ('Đi đường', 'tong_hang_di_duong_sl_t', 'Tổng đi đường', 'tong_hang_di_duong'),
        ]
        fixed_end = [
            ('Dự trữ tối thiểu', 'sl_du_tru_toi_thieu', 'qty'),
            ('Đề xuất đặt mua', 'sl_dat_mua_de_xuat', 'qty'),
            ('Đặt mua chốt', 'sl_dat_mua_chot', 'qty'),
            ('SL mua theo MOQ', 'sl_can_mua_theo_moq', 'qty'),
            ('Đơn giá mua', 'don_gia_mua', 'money'),
            ('Giá trị mua', 'gia_tri_mua_hang', 'money'),
            ('Tồn kho cuối kỳ', 'sl_ton_kho_cuoi_ky', 'qty'),
            ('Ngày vòng quay tồn', 'so_ngay_vong_quay_ton', 'qty2'),
            ('Đơn giá tồn cuối kỳ', 'don_gia_ton_kho_cuoi_ky', 'money'),
            ('Giá trị tồn cuối kỳ', 'gia_tri_ton_kho_cuoi_ky', 'money'),
            ('Ghi chú', 'ghi_chu', 'text'),
        ]

        col_specs = []
        col = 1

        for label, field, kind in fixed_start:
            ws.merge_cells(
                start_row=header_row1, start_column=col,
                end_row=header_row2, end_column=col,
            )
            ws.cell(row=header_row1, column=col, value=label)
            col_specs.append((field, kind))
            col += 1

        for group_label, field_prefix, total_label, total_field in month_groups:
            group_start = col
            ws.merge_cells(
                start_row=header_row1, start_column=group_start,
                end_row=header_row1, end_column=group_start + 3,
            )
            ws.cell(row=header_row1, column=group_start, value=group_label)
            for month_offset, month in enumerate(months):
                ws.cell(
                    row=header_row2, column=col,
                    value='Tháng %s' % month if month else 'T%s' % month_offset,
                )
                col_specs.append((f'{field_prefix}{month_offset}', 'qty'))
                col += 1
            ws.merge_cells(
                start_row=header_row1, start_column=col,
                end_row=header_row2, end_column=col,
            )
            ws.cell(row=header_row1, column=col, value=total_label)
            col_specs.append((total_field, 'qty'))
            col += 1

        for label, field, kind in fixed_end:
            ws.merge_cells(
                start_row=header_row1, start_column=col,
                end_row=header_row2, end_column=col,
            )
            ws.cell(row=header_row1, column=col, value=label)
            col_specs.append((field, kind))
            col += 1

        max_col = col - 1
        row_idx = data_row
        for line in lines:
            for col_idx, (field, kind) in enumerate(col_specs, start=1):
                ws.cell(
                    row=row_idx, column=col_idx,
                    value=self._b5_export_value(line, field, kind),
                )
            row_idx += 1

        self._apply_b5_export_style(ws, header_row1, header_row2, max_col, col_specs)

        ws.column_dimensions['A'].width = 14
        ws.column_dimensions['B'].width = 28
        ws.column_dimensions['C'].width = 12
        ws.column_dimensions['D'].width = 8
        for col_idx in range(5, max_col + 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = 14

        code = (self.code or '').strip()
        if code.upper().startswith('KHVT_'):
            file_suffix = code[5:]
        else:
            file_suffix = code or str(self.id)
        return self._xlsx_download_action(
            wb,
            'Data_KHDVT_%s.xlsx' % file_suffix,
        )

    def action_export_vat_tu_can(self):
        """Xuất Excel bước 3 — layout pivot giống UI (Tháng × Đơn vị KD + Tổng)."""
        self.ensure_one()
        lines = self.tinh_toan_vat_tu_ids
        if not lines:
            raise UserError(_('Chưa có dữ liệu tính toán vật tư để xuất.'))
        if self.state in ('ke_hoach', 'dinh_muc'):
            raise UserError(_('Chỉ export được từ bước Tính toán vật tư trở đi.'))

        months = self._get_horizon_months()
        if len(months) < 4:
            months = (months + [''] * 4)[:4]

        # Đơn vị KD xuất hiện trong B3, sort theo mã
        kd_map = {}
        for line in lines:
            if not line.don_vi_kd_id:
                continue
            cid = line.don_vi_kd_id.id
            code = (line.don_vi_kd_code or '').strip()
            if not code:
                code = (
                    line.don_vi_kd_id.company_code
                    or line.don_vi_kd_id.name
                    or '#%s' % cid
                )
            kd_map[cid] = code
        kd_companies = sorted(kd_map.items(), key=lambda item: str(item[1]))

        # Pivot: 1 dòng / mã NVL
        by_mat = {}
        for line in lines:
            key = (line.ma_vat_tu or '').strip() or ('id:%s' % line.id)
            if key not in by_mat:
                by_mat[key] = {
                    'ma_vat_tu': line.ma_vat_tu or '',
                    'ten_vat_tu': line.ten_vat_tu or '',
                    'don_vi_tinh': (
                        line.don_vi_tinh.display_name if line.don_vi_tinh else ''
                    ),
                    'by_company': {},
                }
            if line.don_vi_kd_id:
                by_mat[key]['by_company'][line.don_vi_kd_id.id] = line
        rows = [by_mat[k] for k in sorted(by_mat.keys())]

        wb = Workbook()
        ws = wb.active
        ws.title = 'Vat tu can'

        ws.cell(row=1, column=1, value='Số chứng từ')
        ws.cell(row=1, column=2, value=self.code or '')
        ws.cell(row=2, column=1, value='Tháng bắt đầu')
        ws.cell(row=2, column=2, value=self.period_month or '')

        header_row1 = 4
        header_row2 = 5
        data_row = 6

        # Meta + specs cho style (qty/text)
        col_specs = []
        col = 1
        for label in ('Mã NVL', 'Tên NVL', 'ĐVT'):
            ws.merge_cells(
                start_row=header_row1, start_column=col,
                end_row=header_row2, end_column=col,
            )
            ws.cell(row=header_row1, column=col, value=label)
            col_specs.append((None, 'text'))
            col += 1

        for month_offset, month in enumerate(months):
            group_start = col
            span = len(kd_companies) + 1  # KD codes + Tổng
            ws.merge_cells(
                start_row=header_row1, start_column=group_start,
                end_row=header_row1, end_column=group_start + span - 1,
            )
            month_label = 'Tháng %s' % month if month else 'T%s' % month_offset
            ws.cell(row=header_row1, column=group_start, value=month_label)
            for _cid, code in kd_companies:
                ws.cell(row=header_row2, column=col, value=code)
                col_specs.append((None, 'qty'))
                col += 1
            ws.cell(row=header_row2, column=col, value='Tổng')
            col_specs.append((None, 'qty'))
            col += 1

        max_col = col - 1
        row_idx = data_row
        for row in rows:
            ws.cell(row=row_idx, column=1, value=row['ma_vat_tu'])
            ws.cell(row=row_idx, column=2, value=row['ten_vat_tu'])
            ws.cell(row=row_idx, column=3, value=row['don_vi_tinh'])
            col_idx = 4
            for month_offset in range(4):
                month_total = 0.0
                for cid, _code in kd_companies:
                    line = row['by_company'].get(cid)
                    qty = getattr(line, 'qty_t%s' % month_offset, 0.0) if line else 0.0
                    qty = qty or 0.0
                    month_total += qty
                    ws.cell(row=row_idx, column=col_idx, value=qty)
                    col_idx += 1
                ws.cell(row=row_idx, column=col_idx, value=month_total)
                col_idx += 1
            row_idx += 1

        self._apply_b5_export_style(ws, header_row1, header_row2, max_col, col_specs)

        ws.column_dimensions['A'].width = 14
        ws.column_dimensions['B'].width = 28
        ws.column_dimensions['C'].width = 10
        for col_idx in range(4, max_col + 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = 12

        code = (self.code or '').strip()
        if code.upper().startswith('KHVT_'):
            file_suffix = code[5:]
        else:
            file_suffix = code or str(self.id)
        return self._xlsx_download_action(
            wb,
            'Data_VatTuCan_%s.xlsx' % file_suffix,
        )

    @staticmethod
    def _b5_export_value(line, field, kind):
        if field == 'don_vi_tinh':
            dvt = line.don_vi_tinh
            return dvt.display_name if dvt else ''
        value = getattr(line, field, False)
        if kind == 'text':
            return value or ''
        if value in (False, None):
            return 0.0 if kind != 'text' else ''
        return value

    def _apply_b5_export_style(self, ws, header_row1, header_row2, max_col, col_specs):
        header_font = Font(name='Times New Roman', size=10, bold=True, color='FFFFFF')
        header_fill = PatternFill(fill_type='solid', fgColor='3F6F8F')
        header_side = Side(style='thin', color='2F556D')
        header_border = Border(
            left=header_side, right=header_side, top=header_side, bottom=header_side,
        )
        label_font = Font(name='Times New Roman', size=10, bold=True)
        base_font = Font(name='Times New Roman', size=10)
        center = Alignment(horizontal='center', vertical='center', wrap_text=True)
        left = Alignment(horizontal='left', vertical='center')
        right = Alignment(horizontal='right', vertical='center')
        qty_fmt = '#,##0.000'
        qty2_fmt = '#,##0.00'
        money_fmt = '#,##0'

        for row_idx in (1, 2):
            ws.cell(row=row_idx, column=1).font = label_font

        for row_idx in (header_row1, header_row2):
            for col_idx in range(1, max_col + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.font = header_font
                cell.fill = header_fill
                cell.border = header_border
                cell.alignment = center
            ws.row_dimensions[row_idx].height = 22

        kind_fmt = {'qty': qty_fmt, 'qty2': qty2_fmt, 'money': money_fmt}
        for row_idx in range(header_row2 + 1, ws.max_row + 1):
            for col_idx, (_, kind) in enumerate(col_specs, start=1):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.font = base_font
                if kind == 'text':
                    cell.alignment = left
                else:
                    cell.alignment = right
                    fmt = kind_fmt.get(kind)
                    if fmt:
                        cell.number_format = fmt

        ws.freeze_panes = ws.cell(row=header_row2 + 1, column=1).coordinate

    _IMPORT_BCU_ACTION_XMLID = 'sonha_vat_tu.action_import_tong_hop_bcu_server'
    _EXPORT_B5_ACTION_XMLID = 'sonha_vat_tu.action_export_kh_dat_vat_tu_server'
    _EXPORT_B3_ACTION_XMLID = 'sonha_vat_tu.action_export_vat_tu_can_server'
    _B3_FORM_VIEW_XMLID = 'sonha_vat_tu.view_ke_hoach_vat_tu_form_b3'
    _B4_FORM_VIEW_XMLID = 'sonha_vat_tu.view_ke_hoach_vat_tu_form_b4'
    _B5_FORM_VIEW_XMLID = 'sonha_vat_tu.view_ke_hoach_vat_tu_form_b5'

    def _toolbar_remove_action(self, toolbar, action_xmlid):
        action = self.env.ref(action_xmlid, raise_if_not_found=False)
        if not action:
            return
        for key in ('action', 'print'):
            items = toolbar.get(key)
            if items:
                toolbar[key] = [
                    item for item in items
                    if item.get('id') != action.id
                ]

    @api.model
    def get_views(self, views, options=None):
        """Ẩn Import BCU / Export B3 / Export B5 khỏi form không đúng bước."""
        res = super().get_views(views, options=options)
        form = res.get('views', {}).get('form')
        if not form or not (options or {}).get('toolbar'):
            return res
        toolbar = form.setdefault('toolbar', {})
        form_view_id = form.get('id')

        b3_view = self.env.ref(self._B3_FORM_VIEW_XMLID, raise_if_not_found=False)
        b4_view = self.env.ref(self._B4_FORM_VIEW_XMLID, raise_if_not_found=False)
        b5_view = self.env.ref(self._B5_FORM_VIEW_XMLID, raise_if_not_found=False)

        if b4_view and form_view_id != b4_view.id:
            self._toolbar_remove_action(toolbar, self._IMPORT_BCU_ACTION_XMLID)
        if b3_view and form_view_id != b3_view.id:
            self._toolbar_remove_action(toolbar, self._EXPORT_B3_ACTION_XMLID)
        if b5_view and form_view_id != b5_view.id:
            self._toolbar_remove_action(toolbar, self._EXPORT_B5_ACTION_XMLID)
        return res

    def get_formview_id(self, access_uid=None):
        """Giữ đúng form view khi reload URL (model + id, không có action)."""
        self.ensure_one()
        if self.workflow_form_view_id:
            return self.workflow_form_view_id.id
        state_view_xmlids = {
            'dinh_muc': 'sonha_vat_tu.view_ke_hoach_vat_tu_form_b2',
            'tinh_toan': 'sonha_vat_tu.view_ke_hoach_vat_tu_form_b3',
            'tong_hop': 'sonha_vat_tu.view_ke_hoach_vat_tu_form_b4',
            'dat_hang': 'sonha_vat_tu.view_ke_hoach_vat_tu_form_b5',
        }
        xmlid = state_view_xmlids.get(self.state)
        if xmlid:
            view = self.env.ref(xmlid, raise_if_not_found=False)
            if view:
                return view.id
        return super().get_formview_id(access_uid=access_uid)

    def _action_open_step(self, action_xmlid):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(action_xmlid)
        action['res_id'] = self.id
        form_views = [
            (view_id, view_type)
            for view_id, view_type in action.get('views', [])
            if view_type == 'form'
        ]
        if form_views:
            action['views'] = form_views
            action['view_mode'] = 'form'
            self.sudo().write({'workflow_form_view_id': form_views[0][0]})
        return action

    def action_open_workflow_sx(self):
        return self._action_open_step('sonha_vat_tu.action_ke_hoach_san_xuat_period')

    def action_open_workflow_vt(self):
        return self._action_open_step('sonha_vat_tu.action_ke_hoach_vat_tu_period')

    def action_open_step_b1(self):
        return self._action_open_step('sonha_vat_tu.action_ke_hoach_vat_tu_period')

    def action_open_step_b2(self):
        return self._action_open_step('sonha_vat_tu.action_ke_hoach_vat_tu_b2')

    def action_open_step_b3(self):
        return self._action_open_step('sonha_vat_tu.action_ke_hoach_vat_tu_b3')

    def action_open_step_b4(self):
        return self._action_open_step('sonha_vat_tu.action_ke_hoach_vat_tu_b4')

    def action_open_step_b5(self):
        return self._action_open_step('sonha_vat_tu.action_ke_hoach_vat_tu_b5')

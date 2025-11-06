from odoo import api, fields, models, _
import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError


class DKVanBanD(models.Model):
    _name = 'dk.vb.d'

    user_duyet = fields.Many2one('res.users', string="Người duyệt", store=True)

    xu_ly = fields.Many2one('dk.xu.ly', string="Tiến trình xử lý", store=True)

    sn_duyet = fields.Float(string="Số ngày duyệt", compute='get_so_ngay_duyet', readonly=False, store=True)
    sn_pb_duyet = fields.Float(string="Số ngày PB duyệt", store=True)

    # Thời gian duyệt (datetime)
    ngay_bd_duyet = fields.Datetime(string="Ngày bắt đầu duyệt", store=True)
    ngay_duyet = fields.Datetime(string="Ngày duyệt", store=True, readonly=True)

    dk_vb_h = fields.Many2one('dk.vb.h', store=True)

    is_approved = fields.Boolean(default=False)
    can_approve = fields.Boolean(
        string="Có thể duyệt",
        compute="_compute_can_approve",
        store=False
    )
    tu_choi = fields.Text("Lý do từ chối", readonly=True, store=True)

    @api.depends('is_approved', 'dk_vb_h.dk_vb_d.is_approved')
    def _compute_can_approve(self):
        for rec in self:

            # Nếu đã duyệt rồi thì ẩn nút
            if rec.is_approved:
                rec.can_approve = False
                continue

            # Nếu không phải người duyệt dòng này → ẩn nút
            if not rec.user_duyet or rec.user_duyet.id != rec.env.uid:
                rec.can_approve = False
                continue

            # Kiểm tra các bước trước đã duyệt hết chưa
            previous_pending = self.env['dk.vb.d'].search_count([
                ('dk_vb_h', '=', rec.dk_vb_h.id),
                ('xu_ly.stt', '<', rec.xu_ly.stt),
                ('is_approved', '=', False),
            ])

            rec.can_approve = previous_pending == 0

    @api.onchange('dk_vb_h', 'xu_ly', 'dk_vb_h.sn_pb', 'dk_vb_h.sn_bdh', 'dk_vb_h.sn_ct')
    @api.depends('dk_vb_h', 'xu_ly', 'dk_vb_h.sn_pb', 'dk_vb_h.sn_bdh', 'dk_vb_h.sn_ct')
    def get_so_ngay_duyet(self):
        for r in self:
            if r.dk_vb_h.sn_pb > 0 and r.xu_ly.stt == 1:
                r.sn_duyet = r.dk_vb_h.sn_pb
            elif r.dk_vb_h.sn_bdh > 0 and r.xu_ly.stt == 2:
                r.sn_duyet = r.dk_vb_h.sn_bdh
            elif r.dk_vb_h.sn_ct > 0 and r.xu_ly.stt == 3:
                r.sn_duyet = r.dk_vb_h.sn_ct
            else:
                pass

    def create(self, vals):
        recs = super(DKVanBanD, self).create(vals)
        for rec in recs:
            rec.ngay_bd_duyet = rec.dk_vb_h.ngay_ct
            self.fill_data_tong_hop(rec)
        return recs

    def write(self, vals):
        for r in self:
            self.env['dk.vb.th'].sudo().search([('dk_vb_d', '=', r.id)]).unlink()
            # self.fill_data_tong_hop(r)
        return super(DKVanBanD, self).write(vals)

    def unlink(self):
        for r in self:
            self.env['dk.vb.th'].sudo().search([('dk_vb_d', '=', r.id)]).unlink()
        return super(DKVanBanD, self).unlink()

    def fill_data_tong_hop(self, rec):
        self.env['dk.vb.th'].sudo().create({
            'dk_vb_d': rec.id or None,
            'dk_vb_h': rec.dk_vb_h.id or None,
            'ngay_ct': str(rec.dk_vb_h.ngay_ct) if rec.dk_vb_h.ngay_ct else None,
            'chung_tu': rec.dk_vb_h.chung_tu or None,
            'ngay_ht': str(rec.dk_vb_h.ngay_ht) if rec.dk_vb_h.ngay_ht else None,
            'dvcs': rec.dk_vb_h.dvcs.id or None,
            'id_loai_vb': rec.dk_vb_h.id_loai_vb.id or None,
            'noi_dung': rec.dk_vb_h.noi_dung or None,
            'tn_pb': rec.dk_vb_h.tn_pb or None,
            'sn_pb': rec.dk_vb_h.sn_pb or None,
            'tn_bdh': rec.dk_vb_h.tn_bdh or None,
            'sn_bdh': rec.dk_vb_h.sn_bdh or None,
            'tn_ct': rec.dk_vb_h.tn_ct or None,
            'sn_ct': rec.dk_vb_h.sn_ct or None,
            'user_duyet': rec.user_duyet.id or None,
            'xu_ly': rec.xu_ly.id or None,
            'sn_duyet': rec.sn_duyet or None,
            'sn_pb_duyet': rec.sn_pb_duyet or None,
            'ngay_bd_duyet': str(rec.ngay_bd_duyet) if rec.ngay_bd_duyet else None,
            'ngay_duyet': str(rec.ngay_duyet) if rec.ngay_duyet else None,
        })

    def action_confirm(self):
        for r in self:
            r.ngay_duyet = datetime.datetime.now()
            r.is_approved = True
            self.fill_ngay_bd_duyet(r)

    def action_cancel(self):
        for r in self:
            self.ensure_one()
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.dk.vb.tu.choi',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_record_id': r.id,
                },
            }

    def fill_ngay_bd_duyet(self, rec):
        list_rec = self.sudo().search([('dk_vb_h', '=', rec.dk_vb_h.id)])
        for r in list_rec:
            r.ngay_bd_duyet = datetime.datetime.now()

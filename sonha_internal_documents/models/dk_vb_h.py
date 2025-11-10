from odoo import api, fields, models, _
import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError


class DKVanBanH(models.Model):
    _name = 'dk.vb.h'
    _order = 'sap_xep,ngay_ct'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    ngay_ct = fields.Date(string="Ngày làm đơn", store=True, default=fields.Date.today, required=True, tracking=True)
    chung_tu = fields.Char(string="Số đơn", store=True, required=True, tracking=True)
    ngay_ht = fields.Date(string="Ngày hoàn thành", store=True, compute="get_ngay_hoan_thanh")
    dvcs = fields.Many2one('res.company', "Đơn vị", default=lambda self: self.env.company, readonly=False, store=True, required=True, tracking=True)

    id_loai_vb = fields.Many2one('dk.loai.vb', string="Loại VB", store=True, required=True, tracking=True)

    noi_dung = fields.Html("Nội dung chi tiết hồ sơ các đơn vị đăng ký", store=True, required=True, tracking=False)

    tn_pb = fields.Boolean(string="Tổng ngày PB", store=True, tracking=True)
    sn_pb = fields.Float(string="Số ngày PB", store=True, tracking=True)

    tn_bdh = fields.Boolean(string="Tổng ngày BDH", store=True, tracking=True)
    sn_bdh = fields.Float(string="Số ngày BDH", store=True, tracking=True)

    tn_ct = fields.Boolean(string="Tổng ngày CT/PCT", store=True, tracking=True)
    sn_ct = fields.Float(string="Số ngày CT/PCT", store=True, tracking=True)

    dk_vb_d = fields.One2many('dk.vb.d', 'dk_vb_h', string="Luồng duyệt", store=True, tracking=True)

    file = fields.Binary(string='File')
    file_name = fields.Char(string="Tên file")
    check_write = fields.Boolean('Kiểm tra', default=False)
    nguoi_tu_choi = fields.Many2one('res.users', string="Người từ chối")
    sap_xep = fields.Integer(string="Sắp xếp", store=True, compute='get_trang_thai_tam')
    status = fields.Selection([
        ('reject', "Từ chối"),
        ('draft', "Nháp"),
        ('done', "Đã xin phê duyệt"),
    ], string='Trạng thái', tracking=True, default='draft')

    @api.depends('dk_vb_d')
    def get_trang_thai_tam(self):
        for r in self:
            for rec in r.dk_vb_d:
                if not rec.is_approved and rec.user_duyet == self.env.uid:
                    r.sap_xep = 2
                else:
                    r.sap_xep = 1

    def _search(self, args, offset=0, limit=None, order=None, access_rights_uid=None):
        context = self.env.context or {}
        show_all = context.get('show_all', False)

        # Nếu show_all=True thì bỏ qua custom filter => hiển thị tất cả
        if not show_all:
            check = 1
        else:
            check = 2
        nguoi_dung = self.env.uid
        quyen = 1 if self.env.user.has_group('sonha_internal_documents.group_admin_van_ban') else 2

        # Gọi function PostgreSQL
        query = "SELECT * FROM fn_lay_vb_duyet(%s, %s, %s)"
        self.env.cr.execute(query, (nguoi_dung, quyen, check))
        rows = self.env.cr.dictfetchall()

        ids = [row["id"] for row in rows if "id" in row]
        args = args + [("id", "in", ids)] if ids else [("id", "=", 0)]

        return super(DKVanBanH, self)._search(
            args,
            offset=offset,
            limit=limit,
            order=order,
            access_rights_uid=access_rights_uid,
        )

    @api.model
    def search_count(self, args):
        ids = self._search(args)
        return len(ids)

    @api.constrains('tn_pb', 'tn_ct', 'tn_bdh', 'sn_pb', 'sn_bdh', 'sn_ct')
    def validate_ngay(self):
        for r in self:
            if r.tn_pb and r.sn_pb <= 0:
                raise ValidationError("Số ngày PB không được bé hơn hoặc hoặc không")
            if r.tn_bdh and r.sn_bdh <= 0:
                raise ValidationError("Số ngày BDH không được bé hơn hoặc hoặc không")
            if r.tn_ct and r.sn_ct <= 0:
                raise ValidationError("Số ngày CT/PCT không được bé hơn hoặc hoặc không")

    @api.constrains('dk_vb_d')
    def validate_chi_tiet(self):
        for r in self:
            if not r.dk_vb_d:
                raise ValidationError("Luồng xử lý không được để trống!")
            for rec in r.dk_vb_d:
                if not rec.user_duyet:
                    raise ValidationError("Người duyệt không được để trống!")
                if not rec.xu_ly:
                    raise ValidationError("Tiến trình xử lý không được để trống!")
                if rec.sn_duyet <= 0:
                    raise ValidationError("Số ngày duyệt không được bé hơn hoặc hoặc không")

    @api.depends('sn_pb', 'sn_bdh', 'sn_ct', 'ngay_ct', 'dk_vb_d')
    def get_ngay_hoan_thanh(self):
        for r in self:
            number = 0
            if r.sn_pb > 0:
                number += r.sn_pb
            else:
                rec = self.env['dk.vb.d'].sudo().search([('dk_vb_h', '=', r.id),
                                                         ('xu_ly.stt', '=', 1)])
                number += sum(rec.mapped('sn_duyet'))

            if r.sn_bdh > 0:
                number += r.sn_bdh
            else:
                rec = self.env['dk.vb.d'].sudo().search([('dk_vb_h', '=', r.id),
                                                         ('xu_ly.stt', '=', 2)])
                number += sum(rec.mapped('sn_duyet'))

            if r.sn_ct > 0:
                number += r.sn_ct
            else:
                rec = self.env['dk.vb.d'].sudo().search([('dk_vb_h', '=', r.id),
                                                         ('xu_ly.stt', '=', 3)])
                number += sum(rec.mapped('sn_duyet'))

            r.ngay_ht = r.ngay_ct + relativedelta(days=number)

    def action_confirm(self):
        Mail = self.env['mail.mail']
        for r in self:
            recipients = []
            if r.nguoi_tu_choi:
                recipients.append(r.nguoi_tu_choi.employee_id)
            else:
                # gửi mail cho list user có stt là 1
                list_stt_1 = self.env['dk.vb.d'].sudo().search([
                    ('dk_vb_h', '=', r.id),
                    ('xu_ly.stt', '=', 1),
                    ('is_approved', '=', False)
                ])
                recipients = list_stt_1.mapped('user_duyet.employee_ids')

            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            link = f"{base_url}/web#id={r.id}&model=dk.vb.h&view_type=form"
            sender_name = r.create_uid.name if r.create_uid else ""
            document_no = r.chung_tu or ""
            document_type = r.id_loai_vb.ten or ""
            send_date = r.create_date.strftime("%d/%m/%Y") if r.create_date else ""

            for partner in recipients:
                subject = f"Hồ sơ cần Anh/Chị phê duyệt"

                body = f"""
                        <p>Kính gửi Anh/Chị {partner.name},</p>

                        <p>Hệ thống xin thông báo hiện đang có 
                        <b>{document_type}</b> đang chờ Anh/Chị xem xét và phê duyệt.</p>

                        <p>Anh/Chị vui lòng truy cập vào hệ thống để kiểm tra và xử lý đơn trong thời gian sớm nhất,
                        nhằm đảm bảo tiến độ công việc.</p>

                        <p><b>Thông tin đơn phê duyệt:</b><br/>
                        • <b>Người gửi:</b> {sender_name}<br/>
                        • <b>Số văn bản:</b> {document_no}<br/>
                        • <b>Loại đơn:</b> <b>{document_type}</b><br/>
                        • <b>Ngày gửi:</b> {send_date}<br/>
                        • <b>Link phê duyệt:</b> <a href="{link}">Nhấn vào đây để xem văn bản</a></p>

                        <p>Trân trọng,<br/>
                        Hệ thống Quản lý Văn bản</p>
                    """
                mail_values = {
                    'subject': subject,
                    'body_html': body,
                    'email_to': partner.work_email,
                }
                Mail.sudo().create(mail_values).sudo().send()
            list_rec_d = self.env['dk.vb.d'].sudo().search([('dk_vb_h', '=', r.id),
                                                            ('is_approved', '=', False)])

            for d in list_rec_d:
                d.ngay_bd_duyet = datetime.datetime.now()

            r.check_write = True
            r.status = 'done'

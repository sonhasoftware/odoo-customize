import json

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class BaoCaoDuAn(models.Model):
    """Persist results returned by ``public.fn_bao_cao_du_an``.

    The database function owns the report columns and can therefore evolve
    independently.  The raw result is retained as JSON in addition to the
    report fields shown in the Odoo interface.
    """

    _name = 'sonha.du.an.bao.cao'
    _description = 'Báo cáo dự án'
    _table = 'bao_cao'
    _order = 'ngay_tao_bao_cao desc, id desc'

    name = fields.Char(string='Tên', required=True, readonly=True)
    tu_ngay = fields.Date(string='Từ ngày', required=True, readonly=True)
    den_ngay = fields.Date(string='Đến ngày', required=True, readonly=True)
    du_an_cha_id = fields.Many2one(
        'project.project', string='Dự án cha', readonly=True,
        ondelete='restrict', index=True,
    )
    stt = fields.Integer(string='STT', readonly=True)
    noi_dung_cv_con = fields.Char(string='Nội dung công việc con', readonly=True)
    ngay_bat_dau = fields.Date(string='Ngày bắt đầu', readonly=True)
    ngay_ket_thuc = fields.Date(string='Ngày kết thúc', readonly=True)
    ten_trang_thai = fields.Text(string='Tên trạng thái', readonly=True)
    tinh_trang_han = fields.Text(string='Tình trạng hạn', readonly=True)
    pt_cv = fields.Float(string='% công việc', readonly=True)
    ns_lam = fields.Text(string='Nhân sự làm', readonly=True)
    in_dam = fields.Integer(string='In đậm', readonly=True)
    du_lieu = fields.Text(string='Dữ liệu báo cáo', required=True, readonly=True)
    ngay_tao_bao_cao = fields.Datetime(
        string='Ngày tạo báo cáo', required=True, readonly=True,
        default=fields.Datetime.now,
    )

    @api.model
    def generate_from_function(self, tu_ngay, den_ngay, du_an_cha_id=False):
        """Run the PostgreSQL report function and save all returned rows.

        ``fn_bao_cao_du_an`` receives dates as ``dd/mm/yyyy`` text, rather
        than Odoo's default ISO date representation.
        """
        if not tu_ngay or not den_ngay:
            raise ValidationError(_("Bạn phải nhập từ ngày và đến ngày."))

        start_date = fields.Date.to_date(tu_ngay)
        end_date = fields.Date.to_date(den_ngay)
        if start_date > end_date:
            raise ValidationError(_("Từ ngày không được lớn hơn đến ngày."))

        # Always call the three-argument function.  PostgreSQL receives NULL
        # when no parent project is selected, rather than invoking a separate
        # two-argument function overload.
        query_params = (
            start_date.strftime('%d/%m/%Y'),
            end_date.strftime('%d/%m/%Y'),
            du_an_cha_id or None,
        )
        query = 'SELECT * FROM public.fn_bao_cao_du_an(%s, %s, %s)'
        self.env.cr.execute(query, query_params)
        rows = self.env.cr.dictfetchall()
        generated_at = fields.Datetime.now()
        project_name = (
            self.env['project.project'].browse(du_an_cha_id).display_name
            if du_an_cha_id else _("Tất cả dự án")
        )
        values = [
            {
                'name': _('%(project)s - dòng %(line)s') % {
                    'project': project_name,
                    'line': index,
                },
                'tu_ngay': tu_ngay,
                'den_ngay': den_ngay,
                'du_an_cha_id': du_an_cha_id,
                'stt': index,
                'noi_dung_cv_con': row.get('noi_dung_cv_con'),
                'ngay_bat_dau': row.get('ngay_bat_dau'),
                'ngay_ket_thuc': row.get('ngay_ket_thuc'),
                'ten_trang_thai': row.get('ten_trang_thai'),
                'tinh_trang_han': row.get('tinh_trang_han'),
                'pt_cv': row.get('pt_cv'),
                'ns_lam': row.get('ns_lam'),
                'in_dam': row.get('in_dam'),
                'du_lieu': json.dumps(row, ensure_ascii=False, default=str, sort_keys=True),
                'ngay_tao_bao_cao': generated_at,
            }
            for index, row in enumerate(rows, start=1)
        ]
        return self.create(values)

    def action_open_generate_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tạo báo cáo dự án'),
            'res_model': 'sonha.du.an.bao.cao.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

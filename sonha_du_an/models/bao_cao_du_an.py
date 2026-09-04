import json

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class BaoCaoDuAn(models.Model):
    """Persist results returned by ``public.fn_bao_cao_du_an``.

    The database function owns the report columns and can therefore evolve
    independently.  Keeping each returned row as JSON prevents an Odoo module
    upgrade from being required every time the function gains a new column.
    """

    _name = 'sonha.du.an.bao.cao'
    _description = 'Báo cáo dự án'
    _table = 'bao_cao'
    _order = 'ngay_tao_bao_cao desc, id desc'

    name = fields.Char(string='Tên', required=True, readonly=True)
    tu_ngay = fields.Date(string='Từ ngày', required=True, readonly=True)
    den_ngay = fields.Date(string='Đến ngày', required=True, readonly=True)
    du_an_cha_id = fields.Many2one(
        'project.project', string='Dự án cha', required=True, readonly=True,
        ondelete='restrict', index=True,
    )
    stt = fields.Integer(string='STT', readonly=True)
    du_lieu = fields.Text(string='Dữ liệu báo cáo', required=True, readonly=True)
    ngay_tao_bao_cao = fields.Datetime(
        string='Ngày tạo báo cáo', required=True, readonly=True,
        default=fields.Datetime.now,
    )

    @api.model
    def generate_from_function(self, tu_ngay, den_ngay, du_an_cha_id):
        """Run the PostgreSQL report function and save all returned rows."""
        if not tu_ngay or not den_ngay or not du_an_cha_id:
            raise ValidationError(_("Bạn phải nhập từ ngày, đến ngày và dự án cha."))
        if tu_ngay > den_ngay:
            raise ValidationError(_("Từ ngày không được lớn hơn đến ngày."))

        self.env.cr.execute(
            'SELECT * FROM public.fn_bao_cao_du_an(%s, %s, %s)',
            (fields.Date.to_string(tu_ngay), fields.Date.to_string(den_ngay), du_an_cha_id),
        )
        rows = self.env.cr.dictfetchall()
        generated_at = fields.Datetime.now()
        values = [
            {
                'name': _('%(project)s - dòng %(line)s') % {
                    'project': self.env['project.project'].browse(du_an_cha_id).display_name,
                    'line': index,
                },
                'tu_ngay': tu_ngay,
                'den_ngay': den_ngay,
                'du_an_cha_id': du_an_cha_id,
                'stt': index,
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

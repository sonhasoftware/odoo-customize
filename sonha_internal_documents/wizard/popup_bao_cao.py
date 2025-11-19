from odoo import models, fields, api
from datetime import datetime, date
import pytz
from calendar import monthrange


class PopupBaoCao(models.TransientModel):
    _name = 'popup.bao.cao'
    _description = 'Chọn khoảng thời gian báo cáo'

    def _default_start_date(self):
        today = date.today()
        return today.replace(day=1)

    def _default_end_date(self):
        today = date.today()
        last_day = monthrange(today.year, today.month)[1]
        return today.replace(day=last_day)

    start_date = fields.Date(string="Ngày bắt đầu", required=True, default=_default_start_date)
    end_date = fields.Date(string="Ngày kết thúc", required=True, default=_default_end_date)

    def _make_naive(self, dt):
        """Convert aware datetime to naive datetime in local timezone."""
        if isinstance(dt, datetime) and dt.tzinfo:
            # chuyển về timezone gốc rồi bỏ tzinfo
            return dt.astimezone(pytz.UTC).replace(tzinfo=None)
        return dt

    def action_confirm(self):
        self.ensure_one()
        date_from = self.start_date.strftime("%Y-%m-%d")
        date_to = self.end_date.strftime("%Y-%m-%d")

        # 1. Xóa dữ liệu cũ
        self.env['bao.cao.van.ban'].search([]).unlink()

        # 2. Gọi hàm SQL
        self._cr.execute("""
                SELECT * FROM fn_bao_cao_duyet_van_ban(%s, %s)
            """, (date_from, date_to))
        rows = self._cr.dictfetchall()

        model = self.env['bao.cao.van.ban']

        for r in rows:

            # Làm sạch dữ liệu datetime: bỏ timezone
            cleaned_vals = {}
            for k, v in r.items():
                cleaned_vals[k] = self._make_naive(v)

            # 3. Tạo bản ghi
            model.create(cleaned_vals)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Báo Cáo Văn Bản',
            'res_model': 'bao.cao.van.ban',
            'view_mode': 'tree',
            'target': 'current',
            'views': [(False, 'tree')],
        }

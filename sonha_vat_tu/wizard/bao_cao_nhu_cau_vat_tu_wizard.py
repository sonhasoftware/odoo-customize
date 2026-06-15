# -*- coding: utf-8 -*-
import calendar
from datetime import date

from odoo import _, fields, models
from odoo.exceptions import UserError


class BaoCaoNhuCauVatTuWizard(models.TransientModel):
    _name = 'bao.cao.nhu.cau.vat.tu.wizard'
    _description = 'Chọn kỳ báo cáo nhu cầu vật tư'

    def _month_selection(self):
        return [(str(month), '%02d' % month) for month in range(1, 13)]

    def _year_selection(self):
        current_year = date.today().year
        return [(str(year), str(year)) for year in range(current_year - 5, current_year + 6)]

    from_month = fields.Selection(
        selection=_month_selection,
        string='Từ tháng',
        required=True,
        default=lambda self: str(date.today().month),
    )
    from_year = fields.Selection(
        selection=_year_selection,
        string='Từ năm',
        required=True,
        default=lambda self: str(date.today().year),
    )
    to_month = fields.Selection(
        selection=_month_selection,
        string='Đến tháng',
        required=True,
    )
    to_year = fields.Selection(
        selection=_year_selection,
        string='Đến năm',
        required=True,
        default=lambda self: str(date.today().year),
    )
    company_id = fields.Many2one(
        'res.company',
        string='Đơn vị',
    )

    def _month_start(self, month, year):
        return date(int(year), int(month), 1)

    def _month_end(self, month, year):
        value = date(int(year), int(month), 1)
        last_day = calendar.monthrange(value.year, value.month)[1]
        return value.replace(day=last_day)

    def action_open_report(self):
        self.ensure_one()
        date_from = self._month_start(self.from_month, self.from_year)
        date_to = self._month_end(self.to_month, self.to_year)
        if date_from > date_to:
            raise UserError(_('Từ tháng không được lớn hơn Đến tháng.'))

        domain = [
            ('month_date', '>=', fields.Date.to_string(date_from)),
            ('month_date', '<=', fields.Date.to_string(date_to)),
        ]
        if self.company_id:
            domain.append(('company_id', '=', self.company_id.id))

        action = self.env.ref('sonha_vat_tu.action_bao_cao_nhu_cau_vat_tu').sudo().read()[0]
        action['domain'] = domain
        action['name'] = _('Báo cáo nhu cầu vật tư')
        action['context'] = {
            'pivot_measures': ['so_luong_vat_tu_can_dung'],
            'vat_tu_company_code_display': True,
        }
        return action

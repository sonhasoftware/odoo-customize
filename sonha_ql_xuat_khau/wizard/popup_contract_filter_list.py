from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta


class PopupContractFilterList(models.TransientModel):
    _name = 'popup.contract.filter.list'

    from_date = fields.Date(string="Từ ngày", store=True)
    to_date = fields.Date(string="Đến ngày", store=True)
    contract_no = fields.Char(string="Số hợp đồng", store=True)
    ship_from = fields.Many2one('exp.config.port', string="Cảng bốc hàng",
                                domain="[('type', '=', 'port_form')]", store=True)
    ship_to = fields.Many2one('exp.config.port', string="Cảng dỡ hàng",
                              domain="[('type', '=', 'port_to')]", store=True)
    country = fields.Many2one('exp.config.country', string="Quốc gia", store=True)

    def action_confirm(self):
        domain = []

        if self.from_date:
            domain.append(('sign_date', '>=', self.from_date))
        if self.to_date:
            domain.append(('sign_date', '<=', self.to_date))
        if self.contract_no:
            domain.append(('contract_no', 'ilike', self.contract_no))
        if self.ship_from:
            domain.append(('shipping_port_from', '=', self.ship_from.id))
        if self.ship_to:
            domain.append(('shipping_port_to', '=', self.ship_to.id))
        if self.country:
            domain.append(('shipping_country', '=', self.country.id))
        return {
            'type': 'ir.actions.act_window',
            'name': 'Hợp đồng',
            'res_model': self.env.context.get('active_model'),
            'view_mode': 'tree,form',
            'domain': domain,
        }
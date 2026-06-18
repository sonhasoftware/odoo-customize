from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta


class PopupInvoicePklChoose(models.TransientModel):
    _name = 'popup.invoice.pkl.choose'

    contract_id = fields.Many2one('exp.contract', string="Hợp đồng", store=True)
    shipment_id = fields.One2many('line.shipment', 'popup_chose', store=True)

    def action_confirm(self):
        list_line = self.shipment_id.sudo().filtered(lambda x: x.radio_tick)
        if not list_line:
            raise ValidationError("Cần chọn ít nhất 1 SO để tạo!")
        list_id = []
        for line in list_line:
            list_id.append(line.shipment_id.id)
        return {
            'name': 'Chọn SO tạo Invoice, Packing List',
            'type': 'ir.actions.act_window',
            'res_model': 'popup.multi.invoice.pkl',
            'view_mode': 'form',
            'view_id': self.env.ref(
                'sonha_ql_xuat_khau.view_popup_multi_invoice_pkl_wizard'
            ).id,
            'target': 'new',
            'context': {
                'default_contract_id': self.contract_id.id,
                'selected_ids': list_id,
            }
        }


class LineShipment(models.TransientModel):
    _name = 'line.shipment'

    contract_id = fields.Many2one('exp.contract', string="Hợp đồng", store=True)
    shipment_id = fields.Many2one('exp.shipment', string="Hàng xuất", store=True)
    popup_chose = fields.Many2one('popup.invoice.pkl.choose', store=True)
    invoice_number = fields.Char(string="Số hóa đơn", store=True)
    so_cont_number = fields.Char(string="Số CONT, Số SO", store=True)
    date_shipment = fields.Char(string="Ngày xuất hàng", store=True)
    radio_tick = fields.Boolean()

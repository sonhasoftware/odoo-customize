from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta


class PopupMultiInvoicePkl(models.TransientModel):
    _name = 'popup.multi.invoice.pkl'

    contract_id = fields.Many2one('exp.contract', string="Hợp đồng", store=True)
    invoice_file = fields.Many2many('ir.attachment',
                                    'exp_popup_invoice_file_attachment_rel',
                                    'document_id',
                                    'attachment_id', string='File Invoice', store=True)
    pkl_file = fields.Many2many('ir.attachment',
                                'exp_popup_pkl_file_attachment_rel',
                                'document_id',
                                'attachment_id', string='File Packing List', store=True)

    def action_confirm(self):
        ids = self.env.context.get('selected_ids', [])
        list_so = self.env['exp.shipment'].sudo().search([('id', 'in', ids)])
        if self.invoice_file or self.pkl_file:
            self.invoice_file.write({
                'res_id': self.id,
            })
            self.pkl_file.write({
                'res_id': self.id,
            })
            for so in list_so:
                if self.invoice_file:
                    so.sudo().write({'file_invoice': [(6, 0, self.invoice_file.ids)]})
                if self.pkl_file:
                    so.sudo().write({'file_pkl': [(6, 0, self.pkl_file.ids)]})


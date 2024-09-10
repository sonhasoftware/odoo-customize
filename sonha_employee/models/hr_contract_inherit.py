from odoo import models, fields, api, _
from lxml import etree
from odoo import models, api


class HrContract(models.Model):
    _inherit = 'hr.contract'

    #
    contract_type_id = fields.Many2one('hr.contract.type', string="Loại hợp đồng", ondelete='cascade')

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        result = super(HrContract, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
                                                             submenu=submenu)
        if view_type == 'form':
            doc = etree.XML(result['arch'])
            state = self.env.context.get('state', self.state)
            for node in doc.xpath("//field[@name='resource_calendar_id']"):
                if state != 'draft':
                    node.set('readonly', '1')
                else:
                    node.set('readonly', '0')
            result['arch'] = etree.tostring(doc, encoding='unicode')
        return result

    def action_confirm(self):
        for r in self:
            if r.state == 'draft':
                r.state = 'open'

    def action_cancel(self):
        for r in self:
            if r.state == 'draft':
                r.state = 'cancel'

    def cancel_confirm(self):
        for r in self:
            if r.state == 'open':
                r.state = 'draft'

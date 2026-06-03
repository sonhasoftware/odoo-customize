from odoo import api, fields, models


class MDMTongHopLine(models.Model):
    _name = 'mdm.tong.hop.line'
    _description = 'Bảng con MDM hàng hóa'

    tong_hop_id = fields.Many2one('mdm.tong.hop', string='Hàng hóa', ondelete='cascade')
    ma_mdm = fields.Char(string='Mã MDM')
    ma_dv = fields.Char(string='Mã đơn vị')
    dvcs = fields.Many2one('res.company', string='ĐVCS')
    ten = fields.Char(related='tong_hop_id.ten', string="Tên", store=True)

    dvt = fields.Many2one('mdm.dvt', string="Đơn vị tính", related='tong_hop_id.dvt', store=True)
    bom_sale = fields.Many2one('bom.sale',  string="Loại Bom Sale", related='tong_hop_id.bom_sale', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get('skip_mdm_api_sync'):
            for record in records.filtered('tong_hop_id'):
                record.tong_hop_id.call_api_insert(record.tong_hop_id, line=record)
        return records

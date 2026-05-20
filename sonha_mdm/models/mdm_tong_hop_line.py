from odoo import fields, models


class MDMTongHopLine(models.Model):
    _name = 'mdm.tong.hop.line'
    _description = 'Bảng con MDM hàng hóa'

    tong_hop_id = fields.Many2one('mdm.tong.hop', string='Hàng hóa', required=True, ondelete='cascade')
    ma_mdm = fields.Char(string='Mã MDM')
    ma_dv = fields.Char(string='Mã đơn vị')
    dvcs = fields.Many2one('res.company', string='ĐVCS')

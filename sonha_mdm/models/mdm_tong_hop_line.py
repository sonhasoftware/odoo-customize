from odoo import fields, models


class MDMTongHopLine(models.Model):
    _name = 'mdm.tong.hop.line'
    _description = 'Bảng con MDM hàng hóa'

    tong_hop_id = fields.Many2one('mdm.tong.hop', string='Hàng hóa', ondelete='cascade')
    ma_mdm = fields.Char(string='Mã MDM')
    ma_dv = fields.Char(string='Mã đơn vị')
    dvcs = fields.Many2one('res.company', string='ĐVCS')
    ten = fields.Char(related='tong_hop_id.ten', string="Tên", stotr=True)

    dvt = fields.Many2one('mdm.dvt', string="Đơn vị tính", related='tong_hop_id.dvt', store=True)
    bom_sale = fields.Many2one('bom.sale',  string="Loại Bom Sale", related='tong_hop_id.bom_sale', store=True)

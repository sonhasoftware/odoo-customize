from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        result = super().session_info()
        if request.session.uid and self.env.user._is_internal():
            result["tree_view_column_layouts"] = self.env[
                "tree.view.column.layout"
            ]._get_layout_map()
        else:
            result["tree_view_column_layouts"] = {}
        return result

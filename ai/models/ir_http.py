# Part of Odoo. See LICENSE file for full copyright and licensing details.

import uuid
from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        result = super().session_info()
        result["ai_session_identifier"] = uuid.uuid4().hex
        return result

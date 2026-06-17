# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.ai import pgvector_is_available


def _auto_install_ai(env):
    try:
        pgvector_is_available(env)
    except Exception:  # noqa: BLE001
        return

    env['ir.module.module'].sudo().search([
        ('name', '=', 'ai'), ('state', '=', 'uninstalled')
    ]).button_install()

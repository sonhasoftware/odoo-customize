# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "AI Text Draft - Accounting",
    'version': '1.0',
    'category': 'Hidden',
    'summary': "AI text draft integration with accounting",
    'depends': ['ai', 'account'],
    'data': [
        'wizard/account_move_send_wizard.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}

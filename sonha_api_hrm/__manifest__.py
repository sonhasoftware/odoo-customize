{
    'name': 'API Module',
    'version': '1.0',
    'summary': 'Module cung cấp API cho hệ thống HRM',
    'author': 'Bạn',
    'depends': ['base', 'sonha_employee', 'sonha_word_slip'],
    'data': [
        'security/ir.model.access.csv',
        'views/remote_timekeeping_views.xml',
    ],
    'installable': True,
    'application': False,
}
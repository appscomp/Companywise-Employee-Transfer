{
    'name': 'Inter Company and Intra Company Employee Transfer',
    'author': 'AppsComp Widgets Pvt Ltd',
    'website': 'www.appcomp.com',
    'category': 'Human Resources',
    'depends': ['base', 'hr', 'apps_branch_master',
                'hr_holidays', 'hr_contract', 'hr_recruitment', 'account', 'om_hr_payroll',
                'om_hr_payroll_account'
                ],
    'summary': "inter company and intra company employee transfer/employee transfer/company transfer/inter company transfer/intra company transfer/multi company employee transfer/employee company transfer/HR transfer/transfer approval/employee",
    "data": [
        'security/ir.model.access.csv',
        'views/employee_fields.xml',
        'views/company_transfer_view.xml',
        'views/grade_selection.xml',
        'data/grade.xml',
        'data/appointment_letter_data.xml',
    ],
    'images': ['static/description/banner.png'],
    #'images': ['static/description/gif.gif'],
    #'price': '42.09',
    'price': '59.54',
    "license": 'OPL-1',
    'installable': True,
    'auto_install': False
}

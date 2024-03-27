{
    "name": "Inter Company and Intra Company Employee Transfer",
    'author': 'AppsComp Widgets Pvt Ltd',
   'category': 'Human Resources',
    "version": "17.0",
    'summary': "Inter-company (Company-to-Company) employee transfer operations involve the movement of employees from"
               " one subsidiary or branch of a company to another. This process, driven by organizational needs such as"
               " skills alignment, project requirements, or strategic workforce planning, aims to optimize human "
               "resources across different parts of the company. Additionally, intra-company transfers within the company"
               " offer another option for managing workforce distribution efficiently",
    'website': 'https://appscomp.com/',
    'images': ['static/description/banner.png'],
    "depends": ['base', 'hr', 'apps_branch_master',
                'hr_holidays', 'hr_contract', 'hr_recruitment', 'account', 'om_hr_payroll',
                'om_hr_payroll_account'],
    'data': [
        'security/ir.model.access.csv',
        'views/employee_fields.xml',
        'views/company_transfer_view.xml',
        'views/grade_selection.xml',
        'data/grade.xml',
        'data/appointment_letter_data.xml',
    ],

    'qweb': [],
    'demo': [],
    'test': [],
    'css': [],
    'js': [],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
    'currency': 'EUR',
    'price': '75',
}

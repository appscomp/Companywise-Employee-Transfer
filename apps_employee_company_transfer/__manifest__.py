{
    'name': 'Inter Company Employee Transfer Operations',
    'author': 'AppsComp Widgets Pvt Ltd',
    'website': 'www.appcomp.com',
    'category': 'Human Resources',
    'depends': ['base', 'hr', 'apps_branch_master',
                'hr_holidays', 'hr_contract', 'hr_recruitment', 'account', 'om_hr_payroll',
                'om_hr_payroll_account'
                ],
    'summary': "Inter company (Company to Company) employee transfer operations involve the movement of "
               "employees from one subsidiary or branch of a company to another. "
               "This process is often driven by organizational needs, such as skills "
               "alignment, project requirements, or strategic workforce planning. "
               "The goal is to optimize human resources across different parts of the "
               "company",
    "data": [
        'security/ir.model.access.csv',
        'views/employee_fields.xml',
        'views/company_transfer_view.xml',
        'views/grade_selection.xml',
        'data/grade.xml',
        'data/appointment_letter_data.xml',
    ],
    'images': ['static/description/banner.png'],
    'price': '47',
    "license": 'OPL-1',
    'installable': True,
    'auto_install': False
}

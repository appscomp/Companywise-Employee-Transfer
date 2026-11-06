{
    'name': 'Inter Company and Intra Company Employee Transfer',
    'author': 'AppsComp Widgets Pvt Ltd',
    'category': 'Human Resources',
    'version': '20.0.1.0.0',
    'summary': 'Inter company and intra company employee transfer with approval workflow, '
               'contract, time off and user access handling',
    'description': """
Employee transfer between companies (inter-company) or inside the same company (intra-company)
with a request, approval, transfer and reverse workflow.

Features
========

* Snapshot of the employee data (company, branch, department, job, grade, managers, contract).
* Approval by the reporting manager or HR, notifications by e-mail, history in the chatter.
* On transfer the running contract is closed, a new contract is created in the target company,
  the employee record and the companies / branches of the user are updated and time off balances are carried over.
* Temporary transfers can be reversed.
* Payroll features are used only when a payroll application is installed.
""",
    'website': 'https://appscomp.com/',
    'depends': ['base', 'mail', 'hr', 'hr_holidays', 'account', 'apps_branch_master'],
    'data': [
        'security/ir.access.csv',
        'data/sequence_data.xml',
        'data/grade.xml',
        'data/mail_template_data.xml',
        'views/grade_selection.xml',
        'views/company_transfer_view.xml',
        'views/employee_fields.xml',
        'views/job_position_views.xml',
        'views/res_company.xml',
    ],
    'assets': {
        'web.assets_tests': ['apps_employee_company_transfer/static/tests/tours/transfer_tour.js'],
    },
    'images': ['static/description/banner.png'],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
    'currency': 'EUR',
    'price': 59.54,
}

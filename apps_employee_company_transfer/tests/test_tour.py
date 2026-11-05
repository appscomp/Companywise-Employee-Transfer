from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestTransferTour(HttpCase):

    def test_transfer_tour(self):
        env = self.env
        company_a = env['res.company'].create({'name': 'Tour Co A'})
        company_b = env['res.company'].create({'name': 'Tour Co B'})
        admin = env.ref('base.user_admin')
        admin.write({'company_ids': [(4, company_a.id), (4, company_b.id)], 'company_id': company_a.id})
        admin.group_ids = [(4, env.ref('hr.group_hr_manager').id)]
        branch_a = env['res.branch'].create({'name': 'TA1', 'code': 'TA1', 'company_id': company_a.id})
        env['res.branch'].create({'name': 'TB1', 'code': 'TB1', 'company_id': company_b.id})
        env['hr.department'].create({'name': 'Tour Dept B', 'company_id': company_b.id})
        env['hr.job'].create({'name': 'Tour Job B', 'company_id': company_b.id})
        dep_a = env['hr.department'].create({'name': 'Tour Dept A', 'company_id': company_a.id})
        env['hr.employee'].create({'name': 'Tour Manager B', 'company_id': company_b.id})
        employee = env['hr.employee'].create({
            'name': 'Tour Employee', 'company_id': company_a.id, 'department_id': dep_a.id,
            'branch': branch_a.id})
        employee.write({'wage': 1000, 'contract_date_start': '2024-01-01'})
        self.start_tour('/odoo', 'apps_employee_company_transfer_tour', login='admin', timeout=120,
                        cookies={'cids': '%d-%d' % (company_a.id, company_b.id)})  # both companies active
        transfer = env['company.transfer'].search([('employee_id', '=', employee.id)])
        self.assertEqual(transfer.state, 'transfer')
        self.assertEqual(employee.company_id, company_b)

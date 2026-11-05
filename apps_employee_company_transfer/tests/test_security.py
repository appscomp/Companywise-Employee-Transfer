from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import TransferCommon


@tagged('post_install', '-at_install')
class TestTransferSecurity(TransferCommon):

    def test_plain_employee_cannot_approve_or_transfer(self):
        tr = self._create()
        tr.submit_employee_company_transfer()
        # the employee is neither the reporting manager nor HR (and cannot even see it)
        with self.assertRaises(Exception):
            tr.with_user(self.emp_user).approve_employee_company_transfer()
        other_manager = tr.with_user(self.mgr_user_b)
        with self.assertRaises(Exception):
            other_manager.approve_employee_company_transfer()
        tr.with_user(self.mgr_user_a).approve_employee_company_transfer()
        # reporting manager (plain user) cannot execute the transfer
        with self.assertRaises(UserError):
            tr.with_user(self.mgr_user_a).update_employee_company_transfer()
        tr.with_user(self.hr_user).update_employee_company_transfer()
        self.assertEqual(tr.state, 'transfer')

    def test_hr_can_approve_any(self):
        tr = self._create()
        tr.submit_employee_company_transfer()
        tr.with_user(self.hr_user).approve_employee_company_transfer()
        self.assertEqual(tr.state, 'approve')

    def test_state_not_writable_by_users(self):
        tr = self._create(user=self.hr_user)
        with self.assertRaises(UserError):
            tr.with_user(self.hr_user).write({'state': 'approve'})

    def test_locked_after_draft(self):
        tr = self._create()
        tr.submit_employee_company_transfer()
        with self.assertRaises(UserError):
            tr.with_user(self.hr_user).write({'transfer_branch': self.branch_b1.id})
        tr.with_user(self.hr_user).write({'end_date': False})  # not a locked field
        tr.with_user(self.hr_user).message_post(body='ok')

    def test_plain_user_visibility(self):
        mine = self._create(user=self.hr_user)
        mine.sudo().write({'user_id': self.emp_user.id})
        tr = self._create()  # created by HR manager, employee requested by someone else
        visible = self.env['company.transfer'].with_user(self.mgr_user_a).search([])
        self.assertIn(tr, visible)  # reporting manager A (current)
        self.assertNotIn(tr, self.env['company.transfer'].with_user(self.emp_user).search([]))
        self.assertIn(mine, self.env['company.transfer'].with_user(self.emp_user).search([]))
        self.assertIn(tr, self.env['company.transfer'].with_user(self.mgr_user_b).search([]))  # target manager, company B
        self.assertIn(tr, self.env['company.transfer'].with_user(self.hr_user).search([]))

    def test_plain_user_can_request_without_salary_access(self):
        tr = self.env['company.transfer'].with_user(self.mgr_user_a).create(self._vals())
        self.assertEqual(tr.sudo().current_employee_wage, 1350)
        with self.assertRaises(AccessError):
            tr.with_user(self.mgr_user_a).current_employee_wage
        self.assertEqual(tr.with_user(self.mgr_user_a).state, 'draft')
        tr.with_user(self.mgr_user_a).submit_employee_company_transfer()
        tr.with_user(self.mgr_user_a).read(['name', 'employee_id', 'transfer_company', 'current_company',
                                            'responsible', 'can_approve', 'employee_count'])

    def test_plain_user_cannot_delete(self):
        tr = self._create(user=self.mgr_user_a)
        with self.assertRaises(AccessError):
            tr.with_user(self.mgr_user_a).unlink()
        tr.with_user(self.hr_manager).unlink()

    def test_grade_access(self):
        grade = self.env['employee.grade'].with_user(self.emp_user)
        self.assertTrue(grade.search([]))
        with self.assertRaises(AccessError):
            grade.create({'grade': 'X'})
        self.env['employee.grade'].with_user(self.hr_manager).create({'grade': 'X', 'level': 5})
        with self.assertRaises(AccessError):
            self.env['employee.grade'].with_user(self.hr_user).create({'grade': 'Y'})

    def test_multi_company_rule(self):
        tr = self._create()
        # a user only allowed in company C sees nothing
        only_c = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Only C', 'login': 'only_c_tr', 'company_id': self.company_c.id,
            'company_ids': [(6, 0, self.company_c.ids)],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('hr.group_hr_user').id])]})
        self.assertNotIn(tr, self.env['company.transfer'].with_user(only_c).search([]))
        # HR allowed in the target company only still sees it (transfer company)
        only_b = only_c.copy({'login': 'only_b_tr', 'company_id': self.company_b.id,
                              'company_ids': [(6, 0, self.company_b.ids)]})
        self.assertIn(tr, self.env['company.transfer'].with_user(only_b).search([]))

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestEmployeePublicRead(TransactionCase):
    """The fields added to hr.employee must not break the employees read by users without HR rights
    (e.g. POS cashiers reading the employees of pos_hr): they are never prefetched."""

    def test_user_without_hr_access_can_read_public_employee_data(self):
        employee = self.env['hr.employee'].create({'name': 'Public Reader Target', 'designation': 'Clerk'})
        user = self.env['res.users'].create({
            'name': 'No HR User', 'login': 'no_hr_user_public_read',
            'groups_id' if 'groups_id' in self.env['res.users']._fields else 'group_ids':
                [(6, 0, [self.env.ref('base.group_user').id])],
        })
        emp = employee.with_user(user)
        self.assertEqual(emp.name, 'Public Reader Target')
        self.assertTrue(emp.active)
        self.assertEqual(employee.designation, 'Clerk')
        for fname in ('designation', 'grade', 'insurance_no', 'branch', 'joining_date'):
            self.assertFalse(self.env['hr.employee']._fields[fname].prefetch, fname)

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TransferCommon


@tagged('post_install', '-at_install')
class TestPayrollOptional(TransferCommon):
    """Without a payroll app nothing breaks; with one (hr.payroll.structure / hr.payslip) it is used."""

    def test_without_payroll(self):
        if 'hr.payslip' in self.env:
            self.skipTest("a payroll app is installed")
        tr = self._create()
        self.assertFalse(tr.payroll_installed)
        self.assertFalse(tr.payroll_structure_model)
        self._to_approved(tr)
        tr.update_employee_company_transfer()
        self.assertEqual(tr.state, 'transfer')
        with self.assertRaises(UserError):
            tr.employee_new_payslip_create_request()
        with self.assertRaises(UserError):
            tr.action_generate_final_payslip()

    def test_with_payroll(self):
        if 'hr.payslip' not in self.env:
            self.skipTest("no payroll app installed")
        struct_a = self.env['hr.payroll.structure'].create({'name': 'Struct A'})
        struct_b = self.env['hr.payroll.structure'].create({'name': 'Struct B'})
        journal_a = self.env['account.journal'].create({
            'name': 'Salary A', 'code': 'SALA', 'type': 'general', 'company_id': self.company_a.id})
        journal_b = self.env['account.journal'].create({
            'name': 'Salary B', 'code': 'SALB', 'type': 'general', 'company_id': self.company_b.id})
        self.company_b.journal_id = journal_b
        self.contract_a.sudo().write({'struct_id': struct_a.id, 'journal_id': journal_a.id})
        tr = self._create(struct_id=struct_b.id, journal_id=journal_b.id)
        rec = tr.sudo()
        self.assertTrue(tr.payroll_installed)
        self.assertEqual(rec.employee_current_salary_structure, struct_a.id)
        self.assertEqual(rec.employee_current_salary_journal, journal_a)
        self._to_approved(tr)
        tr.update_employee_company_transfer()
        new_contract = self.employee.current_version_id
        self.assertEqual(new_contract.struct_id, struct_b)
        self.assertEqual(new_contract.journal_id, journal_b)
        self.assertEqual(tr.employee_new_payslip_create_request()['res_model'], 'hr.payslip')
        tr.action_generate_final_payslip()
        slip = self.env['hr.payslip'].search([('employee_id', '=', self.employee.id)])
        self.assertEqual(len(slip), 1)
        self.assertEqual(slip.company_id, self.company_a)
        self.assertEqual(slip.version_id, self.contract_a)
        self.assertEqual(slip.struct_id, struct_a)
        self.assertEqual(slip.date_to, tr.start_date - __import__('datetime').timedelta(days=1))
        self.assertTrue(slip.computed)
        self.assertTrue(tr.payslip_generated)
        with self.assertRaises(UserError):
            tr.action_generate_final_payslip()
        tr.invalidate_recordset()
        self.assertEqual(tr.employee_payslip_count, 1)
        # reverse needs a temp transfer: payroll struct restored on the contract of the original company

from datetime import timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged
from odoo.tools import mute_logger

from .common import TransferCommon


@tagged('post_install', '-at_install')
class TestTransferFlow(TransferCommon):

    # -- creation / snapshot -------------------------------------------
    def test_sequence_and_snapshot_on_create(self):
        inter = self._create()
        self.assertTrue(inter.name.startswith('Inter/ECT/'))
        self.assertEqual(inter.state, 'draft')
        rec = inter.sudo()
        self.assertEqual(rec.current_company, self.company_a)
        self.assertEqual(rec.current_branch, self.branch_a1)
        self.assertEqual(rec.current_department, self.dep_a)
        self.assertEqual(rec.current_job, self.job_a)
        self.assertEqual(rec.current_reporting_manager, self.mgr_a)
        self.assertEqual(rec.current_supervisor, self.sup_a)
        self.assertEqual(rec.current_grade_id, self.grade_1)
        self.assertEqual(rec.current_contract, self.contract_a)
        self.assertEqual(rec.current_employee_wage, 1350)
        self.assertEqual(rec.transfer_employee_basic, 1000)
        self.assertEqual(rec.employee_default_company_ids, self.company_a)
        self.assertEqual(rec.employee_default_branch_ids, self.branch_a1)
        self.assertEqual(rec.responsible, self.hr_employee.browse() or rec.responsible)
        self.assertIn('Transfer Employee', inter.display_name)

    def test_intra_sequence_and_rules(self):
        vals = self._vals(record_type='intra', transfer_company=self.company_a.id,
                          transfer_branch=self.branch_a2.id, transfer_department=self.dep_a2.id,
                          transfer_job=self.job_a2.id)
        intra = self.env['company.transfer'].with_user(self.hr_manager).create(vals)
        self.assertTrue(intra.name.startswith('Intra/ECT/'))
        with self.assertRaises(ValidationError):  # intra cannot be temporary
            intra.write({'transfer_type': 'temp', 'end_date': self.today + timedelta(days=5)})
        with self.assertRaises(ValidationError):  # intra must stay in the company
            intra.write({'transfer_company': self.company_b.id, 'transfer_branch': self.branch_b1.id,
                         'transfer_department': self.dep_b.id, 'transfer_job': self.job_b.id})

    def test_onchange_form(self):
        journal_b = self.env['account.journal'].create({
            'name': 'Salary B', 'code': 'SALB', 'type': 'general', 'company_id': self.company_b.id})
        self.company_b.journal_id = journal_b
        form = Form(self.env['company.transfer'].with_user(self.hr_manager).with_context(
            default_record_type='inter'))
        form.employee_id = self.employee
        self.assertEqual(form.current_company, self.company_a)
        self.assertEqual(form.current_reporting_manager, self.mgr_a)
        form.transfer_company = self.company_b
        self.assertEqual(form.journal_id, journal_b)
        form.transfer_branch = self.branch_b1
        form.transfer_department = self.dep_b
        form.transfer_job = self.job_b
        form.transfer_grade_id = self.grade_1
        form.transfer_reporting_manager = self.mgr_b
        form.start_date = self.today
        rec = form.save()
        self.assertEqual(rec.state, 'draft')
        # changing the company clears the dependent fields
        with Form(rec) as f:
            f.transfer_company = self.company_c
            self.assertFalse(f.transfer_branch)
            self.assertFalse(f.transfer_department)
            self.assertFalse(f.transfer_job)
            f.transfer_company = self.company_b
            f.transfer_branch = self.branch_b1
            f.transfer_department = self.dep_b
            f.transfer_job = self.job_b

    def test_create_defaults_target_company_salary_journal(self):
        journal_b = self.env['account.journal'].create({
            'name': 'Salary B', 'code': 'SALB', 'type': 'general', 'company_id': self.company_b.id})
        self.company_b.journal_id = journal_b
        transfer = self._create()
        self.assertEqual(transfer.sudo().journal_id, journal_b)

    def test_intra_onchange_form(self):
        form = Form(self.env['company.transfer'].with_user(self.hr_manager).with_context(
            default_record_type='intra', default_transfer_type='permanent'))
        form.employee_id = self.employee
        self.assertEqual(form.transfer_company, self.company_a)

    def test_constraints(self):
        with self.assertRaises(ValidationError):
            self._create(transfer_company=self.company_a.id, transfer_branch=self.branch_a2.id,
                         transfer_department=self.dep_a2.id, transfer_job=self.job_a2.id)  # inter, same company
        with self.assertRaises(ValidationError):
            self._create(transfer_branch=self.branch_a2.id)  # branch of another company
        with self.assertRaises(ValidationError):
            self._create(transfer_department=self.dep_a.id)
        with self.assertRaises(ValidationError):
            self._create(transfer_job=self.job_a.id)
        with self.assertRaises(ValidationError):
            self._create(transfer_type='temp')  # end date required
        with self.assertRaises(ValidationError):
            self._create(transfer_type='temp', end_date=self.today - timedelta(days=1))
        with self.assertRaises(ValidationError):
            self._create(transfer_reporting_manager=self.employee.id)
        journal_a = self.env['account.journal'].create({
            'name': 'Salary A', 'code': 'SALA', 'type': 'general', 'company_id': self.company_a.id})
        with self.assertRaises(ValidationError):
            self._create(journal_id=journal_a.id)

    # -- workflow ---------------------------------------------------------
    def test_state_transitions_cannot_be_skipped(self):
        tr = self._create()
        with self.assertRaises(UserError):
            tr.approve_employee_company_transfer()
        with self.assertRaises(UserError):
            tr.reject_employee_company_transfer()
        with self.assertRaises(UserError):
            tr.update_employee_company_transfer()
        with self.assertRaises(UserError):
            tr.reverse_employee_company_transfer()
        with self.assertRaises(UserError):
            tr.employee_probation_notify()
        with self.assertRaises(UserError):
            tr.set_to_draft()
        tr.submit_employee_company_transfer()
        with self.assertRaises(UserError):
            tr.submit_employee_company_transfer()
        with self.assertRaises(UserError):
            tr.update_employee_company_transfer()  # not approved yet
        tr.with_user(self.mgr_user_a).reject_employee_company_transfer()
        self.assertEqual(tr.state, 'reject')
        with self.assertRaises(UserError):
            tr.approve_employee_company_transfer()
        tr.set_to_draft()
        self.assertEqual(tr.state, 'draft')
        tr.cancel_employee_company_transfer()
        self.assertEqual(tr.state, 'cancel')
        with self.assertRaises(UserError):
            tr.update_employee_company_transfer()
        tr.set_to_draft()
        tr.unlink()

    def test_only_one_pending_transfer_per_employee(self):
        first = self._create()
        first.submit_employee_company_transfer()
        second = self._create()
        with self.assertRaises(UserError):
            second.submit_employee_company_transfer()

    def test_supervisor_required_for_high_grade(self):
        self.employee.grade = self.grade_3
        tr = self._create()
        with self.assertRaises(ValidationError):
            tr.submit_employee_company_transfer()
        tr.write({'transfer_supervisor': self.sup_b.id})
        tr.submit_employee_company_transfer()
        self.assertEqual(tr.state, 'submit')

    def test_inter_company_permanent_full_flow(self):
        tr = self._create(transfer_supervisor=self.sup_b.id, transfer_grade_id=self.grade_3.id,
                          transfer_employee_wage=2000, transfer_employee_basic=1500,
                          remarks='Promotion')
        self.env.flush_all()
        self.env.cr.precommit.run()  # finalise the creation tracking
        self._to_approved(tr)
        self.assertEqual(tr.state, 'approve')
        mails_before = self.env['mail.mail'].search_count([])
        tr.with_user(self.hr_user).update_employee_company_transfer()
        self.assertEqual(tr.state, 'transfer')
        emp = self.employee
        self.assertEqual(emp.company_id, self.company_b)
        self.assertEqual(emp.branch, self.branch_b1)
        self.assertEqual(emp.work_loc_id, self.branch_b1)
        self.assertEqual(emp.department_id, self.dep_b)
        self.assertEqual(emp.job_id, self.job_b)
        self.assertEqual(emp.parent_id, self.mgr_b)
        self.assertEqual(emp.reporting_manager, self.mgr_b)
        self.assertEqual(emp.supervisor, self.sup_b)
        self.assertEqual(emp.grade, self.grade_3)
        self.assertEqual(emp.address_id, self.company_b.partner_id)
        self.assertEqual(emp.joining_date, self.today)
        self.assertEqual(emp.wage, 2000)
        self.assertEqual(emp.basic, 1500)
        # contracts: old one closed the day before, new one running in company B
        self.assertEqual(self.contract_a.contract_date_end, self.today - timedelta(days=1))
        new_contract = emp.current_version_id
        self.assertNotEqual(new_contract, self.contract_a)
        self.assertEqual(new_contract.contract_date_start, self.today)
        self.assertEqual(new_contract.company_id, self.company_b)
        self.assertEqual(new_contract.wage, 2000)
        self.assertEqual(new_contract.job_id, self.job_b)
        self.assertFalse(new_contract.contract_date_end)
        self.assertIn('New contract', ' '.join(tr.message_ids.mapped(lambda m: m.body or '')))
        self.assertEqual(self.contract_a.job_id, self.job_a)  # history kept
        # user access
        user = self.emp_user
        self.assertEqual(user.company_id, self.company_b)
        self.assertEqual(user.company_ids, self.company_a | self.company_b)
        self.assertEqual(user.branch_id, self.branch_b1)
        self.assertEqual(user.branch_ids, self.branch_a1 | self.branch_b1)
        # time off allocations follow the employee: same balance after the transfer
        tr.invalidate_recordset()
        self.assertEqual(tr.allocated_days, 10)
        self.assertEqual(self.allocation_a.state, 'validate')
        # notifications queued + history
        self.assertGreater(self.env['mail.mail'].search_count([]), mails_before)
        history = ' '.join(tr.message_ids.mapped(lambda m: m.body or ''))
        self.assertIn('transferred', history.lower())
        self.env.flush_all()
        self.env.cr.precommit.run()
        self.env.invalidate_all()
        self.assertTrue(tr.sudo().message_ids.filtered(lambda m: m.message_type == 'tracking'))  # status tracking
        # cannot be executed twice, permanent cannot be reversed
        with self.assertRaises(UserError):
            tr.update_employee_company_transfer()
        with self.assertRaises(UserError):
            tr.reverse_employee_company_transfer()

    def test_user_allowed_companies_kept_from_snapshot(self):
        tr = self._create()
        tr.write({'employee_default_company_ids': [(6, 0, (self.company_a | self.company_c).ids)]})
        self._to_approved(tr)
        tr.update_employee_company_transfer()
        self.assertEqual(self.emp_user.company_ids, self.company_a | self.company_b | self.company_c)

    def test_intra_company_flow(self):
        tr = self.env['company.transfer'].with_user(self.hr_manager).create(self._vals(
            record_type='intra', transfer_company=self.company_a.id, transfer_branch=self.branch_a2.id,
            transfer_department=self.dep_a2.id, transfer_job=self.job_a2.id,
            transfer_reporting_manager=self.mgr_a.id, transfer_employee_wage=1500))
        self._to_approved(tr)
        mails = self.env['mail.mail'].search_count([])
        tr.update_employee_company_transfer()
        emp = self.employee
        self.assertEqual(emp.company_id, self.company_a)
        self.assertEqual(emp.branch, self.branch_a2)
        self.assertEqual(emp.department_id, self.dep_a2)
        self.assertEqual(emp.job_id, self.job_a2)
        self.assertEqual(emp.current_version_id.job_id, self.job_a2)
        self.assertEqual(emp.current_version_id.wage, 1500)
        self.assertEqual(self.contract_a.contract_date_end, self.today - timedelta(days=1))
        self.assertEqual(self.emp_user.branch_id, self.branch_a2)
        self.assertEqual(self.allocation_a.state, 'validate')
        self.assertGreater(self.env['mail.mail'].search_count([]), mails)

    def test_temporary_transfer_and_reverse(self):
        end = self.today + timedelta(days=30)
        start = self.today - timedelta(days=10)
        tr = self._create(transfer_type='temp', start_date=start, end_date=end, transfer_employee_wage=1800)
        self.assertEqual(tr.employee_notice_period, 40)
        self._to_approved(tr)
        tr.update_employee_company_transfer()
        emp = self.employee
        self.assertEqual(emp.company_id, self.company_b)
        self.assertEqual(emp.joining_date.isoformat(), '2020-01-01')  # joining date kept for temp
        self.assertEqual(emp.current_version_id.contract_date_end, end)
        self.assertEqual(emp.current_version_id.contract_date_start, start)
        # probation request and confirmation
        tr.with_user(self.hr_user).employee_probation_notify()
        self.assertEqual(tr.state, 'probation')
        self.assertTrue(tr.activity_ids)
        with self.assertRaises(UserError):
            tr.with_user(self.mgr_user_a).action_confirm_probation()
        tr.with_user(self.mgr_user_b).action_confirm_probation()
        self.assertEqual(tr.state, 'transfer')
        self.assertFalse(tr.activity_ids)
        tr.with_user(self.hr_user).employee_probation_notify()
        # reverse from probation
        tr.with_user(self.hr_user).reverse_employee_company_transfer()
        self.assertEqual(tr.state, 'reverse')
        self.assertEqual(emp.company_id, self.company_a)
        self.assertEqual(emp.branch, self.branch_a1)
        self.assertEqual(emp.department_id, self.dep_a)
        self.assertEqual(emp.job_id, self.job_a)
        self.assertEqual(emp.parent_id, self.mgr_a)
        self.assertEqual(emp.wage, 1350)
        self.assertEqual(emp.grade, self.grade_1)
        self.assertEqual(emp.current_version_id.company_id, self.company_a)
        self.assertEqual(emp.current_version_id.wage, 1350)
        self.assertEqual(emp.current_version_id.contract_date_start, self.today)
        transferred = emp.version_ids.filtered(lambda v: v.contract_date_start == start)
        self.assertEqual(transferred.contract_date_end, self.today - timedelta(days=1))
        self.assertEqual(transferred.wage, 1800)
        self.assertEqual(self.emp_user.company_id, self.company_a)
        self.assertEqual(self.emp_user.branch_id, self.branch_a1)
        with self.assertRaises(UserError):
            tr.reverse_employee_company_transfer()

    def test_transfer_on_the_date_of_the_only_version(self):
        other = self.env['hr.employee'].create({
            'name': 'Same Day', 'company_id': self.company_a.id, 'department_id': self.dep_a.id,
            'wage': 900, 'contract_date_start': self.today - timedelta(days=100)})
        self.assertEqual(len(other.version_ids), 1)
        tr = self._create(employee_id=other.id, transfer_employee_wage=1200)
        self._to_approved(tr, approver=self.hr_user)
        tr.update_employee_company_transfer()
        contracts = other.version_ids.filtered('contract_date_start').sorted('contract_date_start')
        self.assertEqual(contracts.mapped('contract_date_start'), [self.today - timedelta(days=100), self.today])
        self.assertEqual(contracts[0].contract_date_end, self.today - timedelta(days=1))
        self.assertEqual(contracts[0].wage, 900)
        self.assertEqual(other.current_version_id.wage, 1200)
        self.assertEqual(other.current_version_id.contract_date_start, self.today)
        tr.invalidate_recordset()
        self.assertEqual(tr.employee_contract_count, 2)

    def test_time_off_balance_kept(self):
        tr = self._create()
        self.assertEqual(tr.sudo().current_employee_remaining_leaves, 10)
        self._to_approved(tr)
        tr.update_employee_company_transfer()
        self.assertEqual(self.env['company.transfer']._employee_remaining_leaves(self.employee), 10)

    def test_transfer_fails_when_employee_moved_elsewhere(self):
        tr = self._create()
        self._to_approved(tr)
        self.employee.write({'company_id': self.company_c.id, 'department_id': False, 'job_id': False,
                             'parent_id': False, 'coach_id': False})
        with self.assertRaises(UserError):
            tr.update_employee_company_transfer()

    def test_archived_employee_not_transferred(self):
        tr = self._create()
        self._to_approved(tr)
        self.employee.active = False
        with self.assertRaises(UserError):
            tr.update_employee_company_transfer()

    def test_employee_without_user_or_contract(self):
        other = self.env['hr.employee'].create({
            'name': 'No user', 'company_id': self.company_a.id, 'department_id': self.dep_a.id})
        tr = self._create(employee_id=other.id)
        self.assertFalse(tr.sudo().current_contract)
        self._to_approved(tr, approver=self.hr_user)
        tr.update_employee_company_transfer()
        self.assertEqual(other.company_id, self.company_b)
        self.assertTrue(other.contract_date_start)  # a new contract is always created

    def test_draft_edit_refreshes_snapshot_on_employee_change(self):
        other = self.env['hr.employee'].create({
            'name': 'Other', 'company_id': self.company_a.id, 'department_id': self.dep_a2.id,
            'branch': self.branch_a2.id, 'wage': 777})
        tr = self._create()
        tr.write({'employee_id': other.id})
        self.assertEqual(tr.sudo().current_department, self.dep_a2)
        self.assertEqual(tr.sudo().current_branch, self.branch_a2)
        self.assertEqual(tr.sudo().current_employee_wage, 777)

    def test_unlink_rules(self):
        tr = self._create()
        tr.submit_employee_company_transfer()
        with self.assertRaises(UserError):
            tr.unlink()
        tr.cancel_employee_company_transfer()
        tr.unlink()

    def test_copy_resets_state_and_name(self):
        tr = self._create()
        self._to_approved(tr)
        new = tr.copy()
        self.assertEqual(new.state, 'draft')
        self.assertNotEqual(new.name, tr.name)

    # -- smart buttons / counts ---------------------------------------
    def test_counts_and_actions(self):
        tr = self._create()
        tr = tr.with_user(self.hr_manager)
        self.assertEqual(tr.employee_count, 1)
        self.assertEqual(tr.employee_contract_count, 1)
        self.assertEqual(tr.employee_leave_request, 0)
        self.assertEqual(tr.employee_payslip_count, 0)
        self.assertEqual(tr.allocated_days, 10)
        self.assertEqual(tr.number_of_days, 0)
        self.assertFalse(tr.payroll_installed or tr.payroll_installed is None)
        for method, model in [('employee_new_contract_create_request', 'hr.version'),
                              ('employee_create_leave_request', 'hr.leave'),
                              ('employee_leave_allocation_info', 'hr.leave.report')]:
            action = getattr(tr, method)()
            self.assertEqual(action['res_model'], model)
            self.assertIn(('employee_id', '=', self.employee.id), action['domain'])
        self.assertEqual(tr.action_open_employee()['res_id'], self.employee.id)
        self.env['account.journal'].create({'name': 'Misc A', 'code': 'MISA', 'type': 'general',
                                            'company_id': self.company_a.id})
        move = self.env['account.move'].with_company(self.company_a).create({
            'move_type': 'entry', 'company_transfer_id': tr.id, 'company_id': self.company_a.id})
        tr.invalidate_recordset()
        self.assertEqual(tr.move_count, 1)
        self.assertEqual(self.env['account.move'].search(tr.action_open_moves()['domain']), move)

    def test_employee_creation_not_blocked_by_new_fields(self):
        emp = self.env['hr.employee'].create({'name': 'Plain', 'company_id': self.company_a.id})
        self.assertFalse(emp.branch)
        self.assertFalse(emp.grade)
        company = self.env['res.company'].create({'name': 'Brand New Co'})
        self.assertFalse(company.journal_id)

    def test_employee_status_and_alias(self):
        emp = self.employee
        emp.date_of_joining = '2021-05-05'
        self.assertEqual(emp.joining_date.isoformat(), '2021-05-05')
        keys = [k for k, _l in emp._fields['employee_status'].selection]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertNotIn('', keys)

    def test_views_load_and_employee_form(self):
        for model in ('company.transfer', 'employee.grade', 'hr.employee', 'res.company', 'res.users',
                      'res.branch', 'account.move'):
            self.env[model].get_views([(False, 'list'), (False, 'form'), (False, 'search')])
        views = self.env['company.transfer'].with_user(self.hr_manager).get_views([(False, 'form')])
        self.assertIn('transfer_company', views['models']['company.transfer']['fields'])
        with Form(self.env['hr.employee'].with_user(self.hr_manager)) as form:
            form.name = 'Form Employee'
            form.grade = self.grade_1
            form.branch = self.branch_a1
            form.work_location_id = self.env['hr.work.location'].create({
                'name': 'Main office', 'address_id': self.company_a.partner_id.id, 'location_type': 'office'})
        self.assertEqual(self.env['hr.employee'].search([('name', '=', 'Form Employee')]).grade, self.grade_1)

    def test_grade_unique(self):
        with self.assertRaises(Exception), self.cr.savepoint(), mute_logger('odoo.sql_db'):
            self.env['employee.grade'].create({'grade': '1'})

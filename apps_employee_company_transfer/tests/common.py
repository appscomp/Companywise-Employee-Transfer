from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase


class TransferCommon(TransactionCase):
    """Two companies with branches, departments, jobs, employees, users, contracts and time off."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        cls.company_a = Company.create({'name': 'Transfer Co A'})
        cls.company_b = Company.create({'name': 'Transfer Co B'})
        cls.company_c = Company.create({'name': 'Transfer Co C (other)'})
        cls.today = fields.Date.context_today(cls.env['company.transfer'])
        Branch = cls.env['res.branch']
        cls.branch_a1 = Branch.create({'name': 'A1', 'code': 'A1', 'company_id': cls.company_a.id})
        cls.branch_a2 = Branch.create({'name': 'A2', 'code': 'A2', 'company_id': cls.company_a.id})
        cls.branch_b1 = Branch.create({'name': 'B1', 'code': 'B1', 'company_id': cls.company_b.id})
        cls.branch_c1 = Branch.create({'name': 'C1', 'code': 'C1', 'company_id': cls.company_c.id})
        Department = cls.env['hr.department']
        cls.dep_a = Department.create({'name': 'Sales A', 'company_id': cls.company_a.id})
        cls.dep_a2 = Department.create({'name': 'Support A', 'company_id': cls.company_a.id})
        cls.dep_b = Department.create({'name': 'Sales B', 'company_id': cls.company_b.id})
        Job = cls.env['hr.job']
        cls.job_a = Job.create({'name': 'Seller A', 'company_id': cls.company_a.id})
        cls.job_a2 = Job.create({'name': 'Lead A', 'company_id': cls.company_a.id})
        cls.job_b = Job.create({'name': 'Seller B', 'company_id': cls.company_b.id})
        cls.grade_1 = cls.env.ref('apps_employee_company_transfer.package_type_01')
        cls.grade_3 = cls.env.ref('apps_employee_company_transfer.package_type_03')

        both = (cls.company_a | cls.company_b | cls.company_c)
        groups = lambda *xmlids: [(6, 0, [cls.env.ref(x).id for x in xmlids])]
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.hr_manager = Users.create({
            'name': 'HR Manager', 'login': 'tr_hr_manager', 'email': 'hrm@example.com',
            'company_id': cls.company_a.id, 'company_ids': [(6, 0, both.ids)],
            'group_ids': groups('base.group_user', 'hr.group_hr_manager'),
        })
        cls.hr_user = Users.create({
            'name': 'HR Officer', 'login': 'tr_hr_user', 'email': 'hru@example.com',
            'company_id': cls.company_a.id, 'company_ids': [(6, 0, both.ids)],
            'group_ids': groups('base.group_user', 'hr.group_hr_user'),
        })
        cls.mgr_user_a = Users.create({
            'name': 'Manager A', 'login': 'tr_mgr_a', 'email': 'mgra@example.com',
            'company_id': cls.company_a.id, 'company_ids': [(6, 0, cls.company_a.ids)],
            'group_ids': groups('base.group_user'),
        })
        cls.mgr_user_b = Users.create({
            'name': 'Manager B', 'login': 'tr_mgr_b', 'email': 'mgrb@example.com',
            'company_id': cls.company_b.id, 'company_ids': [(6, 0, cls.company_b.ids)],
            'group_ids': groups('base.group_user'),
        })
        cls.emp_user = Users.create({
            'name': 'Transfer Employee', 'login': 'tr_emp', 'email': 'emp@example.com',
            'company_id': cls.company_a.id, 'company_ids': [(6, 0, cls.company_a.ids)],
            'group_ids': groups('base.group_user'),
        })
        cls.emp_user.write({'branch_ids': [(6, 0, cls.branch_a1.ids)], 'branch_id': cls.branch_a1.id})
        Employee = cls.env['hr.employee'].with_context(tracking_disable=True)
        cls.mgr_a = Employee.create({'name': 'Manager A', 'company_id': cls.company_a.id,
                                     'user_id': cls.mgr_user_a.id, 'work_email': 'mgra@example.com'})
        cls.mgr_b = Employee.create({'name': 'Manager B', 'company_id': cls.company_b.id,
                                     'user_id': cls.mgr_user_b.id, 'work_email': 'mgrb@example.com'})
        cls.sup_a = Employee.create({'name': 'Supervisor A', 'company_id': cls.company_a.id})
        cls.sup_b = Employee.create({'name': 'Supervisor B', 'company_id': cls.company_b.id})
        cls.hr_employee = Employee.create({'name': 'HR Officer', 'company_id': cls.company_a.id,
                                           'user_id': cls.hr_user.id, 'work_email': 'hru@example.com'})
        cls.employee = Employee.create({
            'name': 'Transfer Employee', 'company_id': cls.company_a.id, 'user_id': cls.emp_user.id,
            'work_email': 'emp@example.com', 'department_id': cls.dep_a.id, 'job_id': cls.job_a.id,
            'parent_id': cls.mgr_a.id, 'reporting_manager': cls.mgr_a.id, 'supervisor': cls.sup_a.id,
            'branch': cls.branch_a1.id, 'work_loc_id': cls.branch_a1.id, 'grade': cls.grade_1.id,
            'basic': 1000, 'housing_allowance': 200, 'travel_allowance': 100, 'other_allowance': 50,
            'wage': 1350, 'joining_date': '2020-01-01',
            'date_version': today_minus(cls.today, 200),
            'contract_date_start': today_minus(cls.today, 200),
        })
        cls.contract_a = cls.employee.current_version_id
        cls.leave_type_a = cls.env['hr.work.entry.type'].create({
            'name': 'Special Leave', 'code': 'SPLTR', 'requires_allocation': True,
            'leave_validation_type': 'no_validation', 'time_off_selectable': True})
        cls.allocation_a = cls.env['hr.leave.allocation'].create({
            'name': 'Initial', 'employee_id': cls.employee.id, 'work_entry_type_id': cls.leave_type_a.id,
            'number_of_days': 10, 'date_from': today_minus(cls.today, 60),
        })
        cls.allocation_a._action_validate()

    def _vals(self, **kw):
        vals = {
            'employee_id': self.employee.id,
            'record_type': 'inter',
            'transfer_type': 'permanent',
            'start_date': self.today,
            'transfer_company': self.company_b.id,
            'transfer_branch': self.branch_b1.id,
            'transfer_department': self.dep_b.id,
            'transfer_job': self.job_b.id,
            'transfer_grade_id': self.grade_1.id,
            'transfer_reporting_manager': self.mgr_b.id,
        }
        vals.update(kw)
        return vals

    def _create(self, user=None, **kw):
        user = user or self.hr_manager
        return self.env['company.transfer'].with_user(user).create(self._vals(**kw))

    def _to_approved(self, transfer, approver=None):
        transfer.with_user(self.hr_manager).submit_employee_company_transfer()
        transfer.with_user(approver or self.mgr_user_a).approve_employee_company_transfer()
        return transfer


def today_minus(day, n):
    return day - timedelta(days=n)

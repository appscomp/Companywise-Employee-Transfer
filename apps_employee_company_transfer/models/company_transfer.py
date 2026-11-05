import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import email_normalize

_logger = logging.getLogger(__name__)

PAYROLL_STRUCTURE_MODEL = 'hr.payroll.structure'
PAYSLIP_MODEL = 'hr.payslip'

# fields that can only be edited while the transfer is a draft
DRAFT_ONLY_FIELDS = {
    'employee_id', 'requested_date', 'start_date', 'transfer_type', 'record_type', 'transfer_company',
    'transfer_branch', 'transfer_department', 'transfer_job', 'transfer_grade_id',
    'transfer_reporting_manager', 'transfer_supervisor', 'struct_id', 'journal_id', 'remarks',
    'employee_default_company_ids', 'employee_default_branch_ids',
    'transfer_employee_basic', 'transfer_employee_housing_allowance', 'transfer_employee_travel_allowance',
    'transfer_employee_other_allowance', 'transfer_employee_wage',
}


class CompanyTransfer(models.Model):
    _name = 'company.transfer'
    _description = "Employee Company Transfer"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    def _default_employee(self):
        return self.env['hr.employee'].sudo().search([('user_id', '=', self.env.uid)], limit=1)

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    user_id = fields.Many2one('res.users', string='User', ondelete='set null', index=True,
                              default=lambda self: self.env.user, readonly=True, copy=False)
    company_id = fields.Many2one('res.company', string='Company', required=True, ondelete='restrict',
                                 index=True, default=lambda self: self.env.company, readonly=True)
    name = fields.Char(string='Employee Company Transfer', required=True, copy=False, readonly=True,
                       index=True, default=lambda self: _('New'),
                       help='A unique sequence number for the Transfer')
    remarks = fields.Text('Remarks', help="Specify notes for the transfer if any")
    requested_date = fields.Date("Requested Date", default=fields.Date.context_today, help="Date of the request",
                                 copy=False)
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True, tracking=True,
                                  help='Select the employee you are going to transfer')
    current_company = fields.Many2one("res.company", string="Current Company")
    transfer_company = fields.Many2one("res.company", string="Transfer to Company", required=True,
                                       tracking=True)
    current_branch = fields.Many2one("res.branch", string="Current Branch")
    transfer_branch = fields.Many2one("res.branch", string="Transfer to Branch", required=True, tracking=True)
    current_department = fields.Many2one("hr.department", string="Current Department")
    transfer_department = fields.Many2one("hr.department", string="Transfer to Department", required=True,
                                          tracking=True)
    current_job = fields.Many2one("hr.job", string="Current Designation")
    transfer_job = fields.Many2one("hr.job", string="Transfer to Designation", required=True, tracking=True)
    current_reporting_manager = fields.Many2one("hr.employee", string="Reporting Manager")
    transfer_reporting_manager = fields.Many2one("hr.employee", string="Transfer to Reporting Manager",
                                                 required=True, tracking=True)
    current_supervisor = fields.Many2one("hr.employee", string="Supervisor")
    transfer_supervisor = fields.Many2one("hr.employee", string="Transfer to Supervisor", tracking=True)
    current_contract = fields.Many2one("hr.version", string="Current Contract")
    current_employee_remaining_leaves = fields.Float(string='Remaining Time Off')
    current_grade_id = fields.Many2one("employee.grade", string="Current Grade")
    current_grade_level = fields.Integer(related='current_grade_id.level', string="Current Grade Level")
    transfer_grade_id = fields.Many2one("employee.grade", string="Transfer Grade", required=True,
                                        tracking=True)

    # salary breakdown (sensitive: HR only)
    current_employee_basic = fields.Float(string='Current Basic', groups="hr.group_hr_user")
    current_employee_housing_allowance = fields.Float(string='Current House Allowance', groups="hr.group_hr_user")
    current_employee_travel_allowance = fields.Float(string='Current Travel Allowance', groups="hr.group_hr_user")
    current_employee_other_allowance = fields.Float(string='Current Other Allowance', groups="hr.group_hr_user")
    current_employee_wage = fields.Float(string='Current Wage', groups="hr.group_hr_user")
    transfer_employee_basic = fields.Float(string='New Basic', tracking=True, groups="hr.group_hr_user")
    transfer_employee_housing_allowance = fields.Float(string='New House Allowance', tracking=True,
                                                       groups="hr.group_hr_user")
    transfer_employee_travel_allowance = fields.Float(string='New Travel Allowance', tracking=True,
                                                      groups="hr.group_hr_user")
    transfer_employee_other_allowance = fields.Float(string='New Other Allowance', tracking=True,
                                                     groups="hr.group_hr_user")
    transfer_employee_wage = fields.Float(string='New Wage', tracking=True, groups="hr.group_hr_user")

    # payroll (only when a payroll app providing hr.payroll.structure is installed)
    payroll_installed = fields.Boolean(compute='_compute_payroll_installed')
    payroll_structure_model = fields.Char(compute='_compute_payroll_installed')
    employee_current_salary_structure = fields.Many2oneReference(
        model_field='payroll_structure_model', string='Current Structure', groups="hr.group_hr_user")
    employee_current_salary_journal = fields.Many2one('account.journal', string='Current Journal',
                                                      groups="hr.group_hr_user")
    struct_id = fields.Many2oneReference(
        model_field='payroll_structure_model', string='Structure', groups="hr.group_hr_user",
        help="Salary structure of the new contract (only with a payroll app installed).")
    journal_id = fields.Many2one(
        'account.journal', string="Salary Journal", groups="hr.group_hr_user",
        domain="[('company_id', '=', transfer_company), ('type', 'not in', ['sale', 'purchase'])]",
        help="Salary journal in the target company (default: the one configured on the company).")
    payslip_generated = fields.Boolean(string="Final Payslip Generated", copy=False, readonly=True)

    # default access of the user account
    employee_default_company = fields.Many2one("res.company", string="Default Company")
    employee_default_company_ids = fields.Many2many(
        'res.company', 'company_transfer_default_company_rel', 'transfer_id', 'company_id',
        string='Default Allowed Companies',
        help="Companies the user of the employee is allowed in after the transfer "
             "(the target company is always added).")
    employee_default_branch = fields.Many2one("res.branch", string="Default Branch")
    employee_default_branch_ids = fields.Many2many(
        'res.branch', 'company_transfer_default_branch_rel', 'transfer_id', 'branch_id',
        string='Default Allowed Branches',
        help="Branches the user of the employee is allowed in after the transfer "
             "(the target branch is always added).")
    carried_allocation_ids = fields.Many2many(
        'hr.leave.allocation', 'company_transfer_allocation_rel', 'transfer_id', 'allocation_id',
        string='Carried Over Time Off Allocations', copy=False, readonly=True)

    state = fields.Selection(
        [('draft', 'Draft'),
         ('cancel', 'Cancelled'),
         ('submit', 'Waiting for Reporting Manager Approval'),
         ('reverse_approve', 'Waiting for Reversal Approval'),
         ('approve', 'Approved'),
         ('reverse', 'Reversed'),
         ('reject', 'Rejected'),
         ('probation', 'Request for Probation Approval'),
         ('transfer', 'Transferred')],
        string='Status', readonly=True, copy=False, default='draft', tracking=True, index=True,
        help=" * 'Draft': the transfer is created and not submitted yet.\n"
             " * 'Waiting for Reporting Manager Approval': submitted, waiting for the approval.\n"
             " * 'Approved': the transfer can be executed by HR.\n"
             " * 'Transferred': the employee, contract and user access were moved to the target company.\n"
             " * 'Request for Probation Approval': a probation approval was requested after a temporary transfer.\n"
             " * 'Reversed': the temporary transfer was reversed, the employee is back in the original company.\n"
             " * 'Cancelled' / 'Rejected': the transfer will not be executed.")
    start_date = fields.Date("Start Date", required=True, default=fields.Date.context_today,
                             help="Date from which the employee works in the target company.")
    end_date = fields.Date("End Date", copy=False,
                           help="Last day of a temporary transfer.")
    transfer_type = fields.Selection(
        [('temp', 'Temporary'),
         ('permanent', 'Permanent')],
        string='Transfer Type', required=True, default='permanent')
    record_type = fields.Selection([('inter', 'INTER'), ('intra', 'INTRA')], string='Record Type',
                                   required=True, default='inter', readonly=True)
    responsible = fields.Many2one('hr.employee', string='Requested By', default=_default_employee,
                                  readonly=True, copy=False, help="Responsible person for the transfer")
    can_approve = fields.Boolean(compute='_compute_can_approve')
    can_transfer = fields.Boolean(compute='_compute_can_approve')
    employee_count = fields.Integer(compute='_compute_counts')
    employee_contract_count = fields.Integer(compute='_compute_counts', string='Contracts')
    employee_payslip_count = fields.Integer(compute='_compute_counts', string='Payslips')
    employee_leave_request = fields.Integer(compute='_compute_counts', string='Leave Requests')
    move_count = fields.Integer(compute='_compute_counts', string='Journal Entries')
    employee_notice_period = fields.Integer(compute='_compute_notice_period', string='Days')
    number_of_days = fields.Float(string='Time Off Taken', compute='_compute_leaves')
    allocated_days = fields.Float(string='Time Off Allocated', compute='_compute_leaves')
    image_field = fields.Binary(string="Image", related='employee_id.image_128', readonly=True)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('start_date', 'end_date', 'transfer_type')
    def _check_dates(self):
        for rec in self:
            if rec.transfer_type == 'temp' and not rec.end_date:
                raise ValidationError(_("The end date is required for a temporary transfer."))
            if rec.end_date and rec.start_date and rec.end_date < rec.start_date:
                raise ValidationError(_("End Date should be greater than start date."))

    @api.constrains('record_type', 'current_company', 'transfer_company')
    def _check_companies(self):
        for rec in self:
            if not rec.current_company:
                continue
            if rec.record_type == 'inter' and rec.current_company == rec.transfer_company:
                raise ValidationError(_(
                    "Current Company and Transferred Company cannot be the same for %s.",
                    rec.employee_id.name))
            if rec.record_type == 'intra' and rec.current_company != rec.transfer_company:
                raise ValidationError(_(
                    "An intra-company transfer must stay in the company of the employee (%s).",
                    rec.current_company.name))

    @api.constrains('record_type', 'transfer_type')
    def _check_intra_permanent(self):
        for rec in self:
            if rec.record_type == 'intra' and rec.transfer_type != 'permanent':
                raise ValidationError(_("An intra-company transfer can only be permanent."))

    @api.constrains('transfer_company', 'transfer_branch', 'transfer_department', 'transfer_job',
                    'journal_id', 'employee_id', 'transfer_reporting_manager', 'transfer_supervisor')
    def _check_target_consistency(self):
        for rec in self.sudo():
            company = rec.transfer_company
            if rec.transfer_branch.company_id != company:
                raise ValidationError(_("The branch %(branch)s does not belong to company %(company)s.",
                                        branch=rec.transfer_branch.display_name, company=company.name))
            if rec.transfer_department.company_id and rec.transfer_department.company_id != company:
                raise ValidationError(_("The department %(dep)s does not belong to company %(company)s.",
                                        dep=rec.transfer_department.display_name, company=company.name))
            if rec.transfer_job.company_id and rec.transfer_job.company_id != company:
                raise ValidationError(_("The job position %(job)s does not belong to company %(company)s.",
                                        job=rec.transfer_job.display_name, company=company.name))
            if rec.journal_id.company_id and rec.journal_id.company_id != company:
                raise ValidationError(_("The salary journal %(journal)s does not belong to company %(company)s.",
                                        journal=rec.journal_id.display_name, company=company.name))
            if rec.employee_id in (rec.transfer_reporting_manager, rec.transfer_supervisor):
                raise ValidationError(_("An employee cannot be his own reporting manager or supervisor."))

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends_context('uid')
    def _compute_payroll_installed(self):
        installed = PAYROLL_STRUCTURE_MODEL in self.env and PAYSLIP_MODEL in self.env
        for rec in self:
            rec.payroll_installed = installed
            rec.payroll_structure_model = PAYROLL_STRUCTURE_MODEL if installed else False

    @api.depends('current_reporting_manager', 'transfer_reporting_manager', 'state')
    @api.depends_context('uid')
    def _compute_can_approve(self):
        user = self.env.user
        is_hr = user.has_group('hr.group_hr_user')
        for rec in self:
            rec.can_transfer = is_hr
            rec.can_approve = is_hr or user == rec.sudo().current_reporting_manager.user_id

    @api.depends('employee_id')
    def _compute_counts(self):
        employees = self.employee_id
        contract_counts = self._count_contracts(employees)
        leave_counts = self._count_by_employee('hr.leave', employees)
        payslip_counts = (self._count_by_employee(PAYSLIP_MODEL, employees)
                          if PAYSLIP_MODEL in self.env else {})
        move_counts = {
            move.id: count for move, count in self.env['account.move'].sudo()._read_group(
                [('company_transfer_id', 'in', self.ids)], ['company_transfer_id'], ['__count'])
        } if self.ids else {}
        for rec in self:
            emp = rec.employee_id.id
            rec.employee_count = 1 if emp else 0
            rec.employee_contract_count = contract_counts.get(emp, 0)
            rec.employee_leave_request = leave_counts.get(emp, 0)
            rec.employee_payslip_count = payslip_counts.get(emp, 0)
            rec.move_count = move_counts.get(rec.id, 0)

    @api.model
    def _count_contracts(self, employees):
        """Number of contracts (distinct contract start dates among the versions) per employee."""
        if not employees:
            return {}
        counts = {}
        for employee, start in self.env['hr.version'].sudo().with_context(active_test=False)._read_group(
                [('employee_id', 'in', employees.ids), ('contract_date_start', '!=', False)],
                ['employee_id', 'contract_date_start:day']):
            counts[employee.id] = counts.get(employee.id, 0) + 1
        return counts

    @api.model
    def _count_by_employee(self, model, employees):
        if not employees:
            return {}
        return {
            employee.id: count for employee, count in self.env[model].sudo().with_context(
                active_test=False)._read_group([('employee_id', 'in', employees.ids)], ['employee_id'], ['__count'])
        }

    @api.depends('transfer_type', 'start_date', 'end_date')
    def _compute_notice_period(self):
        for rec in self:
            if rec.transfer_type == 'temp' and rec.start_date and rec.end_date:
                rec.employee_notice_period = (rec.end_date - rec.start_date).days
            else:
                rec.employee_notice_period = 0

    @api.depends('employee_id')
    def _compute_leaves(self):
        employees = self.employee_id
        allocated = {}
        taken = {}
        if employees:
            for employee, total in self.env['hr.leave.allocation'].sudo()._read_group(
                    [('employee_id', 'in', employees.ids), ('state', '=', 'validate')],
                    ['employee_id'], ['number_of_days:sum']):
                allocated[employee.id] = total
            for employee, total in self.env['hr.leave'].sudo()._read_group(
                    [('employee_id', 'in', employees.ids), ('state', '=', 'validate')],
                    ['employee_id'], ['number_of_days:sum']):
                taken[employee.id] = total
        for rec in self:
            rec.allocated_days = allocated.get(rec.employee_id.id, 0.0)
            rec.number_of_days = taken.get(rec.employee_id.id, 0.0)

    @api.depends('name', 'employee_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s - %s' % (rec.name, rec.employee_id.name) if rec.employee_id else rec.name

    # ------------------------------------------------------------------
    # Snapshot of the employee
    # ------------------------------------------------------------------
    def _contract_payroll_values(self, contract):
        """Payroll values read dynamically from the contract version (only if a payroll app added them)."""
        vals = {}
        if 'struct_id' in contract._fields and contract.struct_id:
            vals['employee_current_salary_structure'] = contract.struct_id.id
            vals['struct_id'] = contract.struct_id.id
        if 'journal_id' in contract._fields and contract.journal_id:
            vals['employee_current_salary_journal'] = contract.journal_id.id
        return vals

    def _employee_snapshot_vals(self, employee):
        """Values copied from the employee when it is selected (done with sudo: contains HR data)."""
        employee = employee.sudo()
        user = employee.user_id
        contract = employee.current_version_id
        vals = {
            'current_company': employee.company_id.id,
            'current_branch': employee.branch.id,
            'current_department': employee.department_id.id,
            'current_job': employee.job_id.id,
            'current_reporting_manager': (employee.reporting_manager or employee.parent_id).id,
            'current_supervisor': employee.supervisor.id,
            'current_grade_id': employee.grade.id,
            'transfer_grade_id': employee.grade.id,
            'current_contract': contract.id if contract.contract_date_start else False,
            'current_employee_remaining_leaves': self._employee_remaining_leaves(employee),
            'employee_default_company': user.company_id.id,
            'employee_default_company_ids': [(6, 0, user.company_ids.ids)],
            'employee_default_branch': user.branch_id.id,
            'employee_default_branch_ids': [(6, 0, user.branch_ids.ids)],
            'current_employee_basic': employee.basic,
            'current_employee_housing_allowance': employee.housing_allowance,
            'current_employee_travel_allowance': employee.travel_allowance,
            'current_employee_other_allowance': employee.other_allowance,
            'current_employee_wage': employee.wage,
            'transfer_employee_basic': employee.basic,
            'transfer_employee_housing_allowance': employee.housing_allowance,
            'transfer_employee_travel_allowance': employee.travel_allowance,
            'transfer_employee_other_allowance': employee.other_allowance,
            'transfer_employee_wage': employee.wage,
            'employee_current_salary_structure': False,
            'employee_current_salary_journal': False,
            'struct_id': False,
        }
        if PAYROLL_STRUCTURE_MODEL in self.env:
            vals.update(self._contract_payroll_values(contract))
        return vals

    @api.model
    def _employee_remaining_leaves(self, employee):
        allocations = self.env['hr.leave.allocation'].sudo().search([
            ('employee_id', '=', employee.id), ('state', '=', 'validate')])
        return sum(allocations.mapped(lambda a: a.number_of_days - a.leaves_taken))

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if not self.employee_id:
            return
        for fname, value in self._employee_snapshot_vals(self.employee_id).items():
            field = self._fields[fname]
            if field.type == 'many2many':
                value = self.env[field.comodel_name].browse(value[0][2])
            elif field.type in ('many2one', 'many2oneReference'):
                value = value or False
            self[fname] = value
        if self.record_type == 'intra':
            self.transfer_company = self.employee_id.company_id
            self.transfer_type = 'permanent'

    @api.onchange('transfer_company')
    def _onchange_transfer_company(self):
        company = self.transfer_company
        if self.transfer_branch.company_id != company:
            self.transfer_branch = False
        if self.transfer_department.company_id and self.transfer_department.company_id != company:
            self.transfer_department = False
        if self.transfer_job.company_id and self.transfer_job.company_id != company:
            self.transfer_job = False
        journal = self.sudo().journal_id
        if journal.company_id != company:
            self.journal_id = company.sudo().journal_id

    @api.onchange('transfer_department')
    def _onchange_transfer_department(self):
        if self.transfer_job and self.transfer_job.department_id and \
                self.transfer_job.department_id != self.transfer_department:
            self.transfer_job = False

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        sudo_vals = []
        for vals in vals_list:
            record_type = vals.get('record_type') or 'inter'
            vals['record_type'] = record_type
            if not vals.get('name') or vals.get('name') == _('New'):
                code = 'company.transfer' if record_type == 'inter' else 'intra.company.transfer'
                vals['name'] = self.env['ir.sequence'].next_by_code(code) or _('New')
            if record_type == 'intra':
                vals.setdefault('transfer_type', 'permanent')
            snapshot = {}
            if vals.get('employee_id'):
                employee = self.env['hr.employee'].browse(vals['employee_id'])
                snapshot = self._employee_snapshot_vals(employee)
                # keep what the user explicitly entered, complete the rest
                snapshot = {k: v for k, v in snapshot.items() if k not in vals}
                if record_type == 'intra':
                    snapshot.setdefault('transfer_company', employee.sudo().company_id.id)
                    vals.setdefault('transfer_company', employee.sudo().company_id.id)
            sudo_vals.append(snapshot)
        records = super().create(vals_list)
        # sensitive/snapshot data written with sudo so that non-HR requesters can create requests
        for rec, snapshot in zip(records, sudo_vals):
            if snapshot:
                rec.sudo().write({k: v for k, v in snapshot.items()})
        return records

    def write(self, vals):
        if not self.env.su:
            if 'state' in vals:
                raise UserError(_("The status can only be changed with the workflow buttons."))
            locked = DRAFT_ONLY_FIELDS & set(vals)
            if locked and any(rec.state != 'draft' for rec in self):
                raise UserError(_("Only a draft transfer can be modified. Set it back to draft first."))
        res = super().write(vals)
        if 'employee_id' in vals and not self.env.su:
            for rec in self.filtered(lambda r: r.state == 'draft' and r.employee_id):
                snapshot = rec._employee_snapshot_vals(rec.employee_id)
                rec.sudo().write({k: v for k, v in snapshot.items() if k not in vals})
        return res

    def unlink(self):
        if any(rec.state not in ('draft', 'cancel', 'reject') for rec in self):
            raise UserError(_("Only draft, cancelled or rejected transfers can be deleted."))
        return super().unlink()

    def copy_data(self, default=None):
        default = dict(default or {})
        default.setdefault('name', _('New'))
        return super().copy_data(default)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _check_state(self, allowed, action):
        for rec in self:
            if rec.state not in allowed:
                raise UserError(_(
                    "You cannot %(action)s the transfer %(name)s in status '%(state)s'.",
                    action=action, name=rec.name,
                    state=dict(self._fields['state']._description_selection(self.env))[rec.state]))

    def _check_approver(self, action):
        for rec in self:
            if not rec._user_can_approve():
                raise UserError(_(
                    "You are not allowed to %s this transfer.\n"
                    "Only the reporting manager or HR can do it.", action))

    def _user_can_approve(self):
        """True when the current user is the current reporting manager or an HR officer."""
        self.ensure_one()
        user = self.env.user
        return user.has_group('hr.group_hr_user') or \
            user == self.sudo().current_reporting_manager.user_id

    def _check_hr(self):
        if not self.env.user.has_group('hr.group_hr_user'):
            raise UserError(_("You are not allowed to execute the transfer. Only HR can do it."))

    def _get_form_url(self):
        self.ensure_one()
        return '%s/odoo/action-%s/%d' % (
            self.get_base_url(),
            self.env.ref('apps_employee_company_transfer.action_view_%s_employee_company_transfers' % (
                'inter' if self.record_type == 'inter' else 'intra')).id,
            self.id)

    def _send_notification(self, xmlid, to_employees, cc_employees=None):
        """Queue the notification e-mail and keep a trace in the chatter."""
        template = self.env.ref(xmlid, raise_if_not_found=False)
        for rec in self:
            emails = lambda emps: ','.join(sorted({
                email_normalize(e.work_email) for e in emps.sudo() if e.work_email and email_normalize(e.work_email)}))
            email_to = emails(to_employees)
            if not template or not email_to:
                rec.message_post(body=_("No e-mail sent: no recipient with a work e-mail address."))
                continue
            template.sudo().with_context(url=rec._get_form_url()).send_mail(
                rec.id, force_send=False, email_values={
                    'email_to': email_to, 'email_cc': emails(cc_employees or rec.env['hr.employee'])})

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def submit_employee_company_transfer(self):
        self._check_state(['draft'], _("submit"))
        for rec in self:
            if rec.sudo().current_company != rec.sudo().employee_id.company_id:
                raise UserError(_("The company of %s changed since the request was created. "
                                  "Please select the employee again.", rec.employee_id.name))
            if rec.current_grade_id.level > 2 and not rec.transfer_supervisor:
                raise ValidationError(_(
                    "A supervisor is required for an employee with grade %s.", rec.current_grade_id.grade))
            if self.search_count([('employee_id', '=', rec.employee_id.id), ('id', '!=', rec.id),
                                  ('state', 'in', ('submit', 'approve'))]):
                raise UserError(_("Another transfer of %s is already waiting for approval or execution.",
                                  rec.employee_id.name))
            rec.sudo().write({'state': 'submit'})
            rec.message_post(body=_("%s transfer submitted for approval.", rec._record_type_label()))
            rec._send_notification(
                'apps_employee_company_transfer.email_template_request_for_company_company_transfer_submit_new',
                rec.current_reporting_manager)
        return True

    def _record_type_label(self):
        self.ensure_one()
        return dict(self._fields['record_type']._description_selection(self.env))[self.record_type].title()

    def approve_employee_company_transfer(self):
        self._check_state(['submit'], _("approve"))
        self._check_approver(_("approve"))
        for rec in self:
            rec.sudo().write({'state': 'approve'})
            rec.message_post(body=_("Transfer approved by %s.", self.env.user.name))
            rec._send_notification(
                'apps_employee_company_transfer.email_template_request_for_company_company_transfer_approved',
                rec.employee_id, rec.transfer_reporting_manager)
        return True

    def reject_employee_company_transfer(self):
        self._check_state(['submit'], _("reject"))
        self._check_approver(_("reject"))
        for rec in self:
            rec.sudo().write({'state': 'reject'})
            rec.message_post(body=_("Transfer rejected by %s.", self.env.user.name))
            rec._send_notification(
                'apps_employee_company_transfer.email_template_request_for_company_company_transfer_rejected',
                rec.employee_id, rec.transfer_reporting_manager)
        return True

    def set_to_draft(self):
        self._check_state(['cancel', 'reject'], _("reset to draft"))
        for rec in self:
            rec.sudo().write({'state': 'draft'})
            rec.message_post(body=_("Transfer set back to draft."))
        return True

    def cancel_employee_company_transfer(self):
        self._check_state(['draft', 'submit', 'approve'], _("cancel"))
        for rec in self:
            if rec.state != 'draft' and not (
                    rec._user_can_approve() or rec.sudo().responsible.user_id == self.env.user):
                raise UserError(_("Only the requester, the reporting manager or HR can cancel this transfer."))
            rec.sudo().write({'state': 'cancel'})
            rec.message_post(body=_("Transfer cancelled by %s.", self.env.user.name))
            rec._send_notification(
                'apps_employee_company_transfer.email_template_request_for_company_company_transfer_cancelled',
                rec.employee_id, rec.transfer_reporting_manager)
        return True

    def employee_probation_notify(self):
        """Request the approval of the probation of an employee transferred temporarily."""
        self._check_state(['transfer'], _("request the probation approval of"))
        for rec in self:
            if rec.transfer_type != 'temp':
                raise UserError(_("The probation request is only available for temporary transfers."))
            rec.sudo().write({'state': 'probation'})
            manager_user = rec.sudo().transfer_reporting_manager.user_id
            if manager_user:
                rec.sudo().activity_schedule(
                    'mail.mail_activity_data_todo', user_id=manager_user.id,
                    summary=_("Probation approval of %s", rec.employee_id.name))
            rec.message_post(body=_("Probation approval requested for %s.", rec.employee_id.name))
        return True

    def action_confirm_probation(self):
        self._check_state(['probation'], _("confirm the probation of"))
        for rec in self:
            if not (self.env.user.has_group('hr.group_hr_user')
                    or self.env.user == rec.sudo().transfer_reporting_manager.user_id):
                raise UserError(_("Only the new reporting manager or HR can confirm the probation."))
            rec.sudo().write({'state': 'transfer'})
            rec.sudo().activity_ids.action_feedback(feedback=_("Probation confirmed."))
            rec.message_post(body=_("Probation confirmed by %s.", self.env.user.name))
        return True

    # ------------------------------------------------------------------
    # Transfer execution
    # ------------------------------------------------------------------
    def update_employee_company_transfer(self):
        self._check_hr()
        self._check_state(['approve'], _("execute"))
        for rec in self:
            rec._execute_move(to_target=True)
            rec.sudo().write({'state': 'transfer'})
            rec.message_post(body=_(
                "Employee transferred to %(company)s / %(branch)s.",
                company=rec.transfer_company.name, branch=rec.transfer_branch.display_name))
            rec._send_notification(
                'apps_employee_company_transfer.email_template_request_for_company_company_transfer_approved',
                rec.employee_id, rec.transfer_reporting_manager | rec.current_reporting_manager)
        return True

    def reverse_employee_company_transfer(self):
        self._check_hr()
        self._check_state(['transfer', 'probation'], _("reverse"))
        for rec in self:
            if rec.transfer_type != 'temp':
                raise UserError(_("Only a temporary transfer can be reversed."))
            rec._execute_move(to_target=False)
            rec.sudo().write({'state': 'reverse'})
            rec.message_post(body=_("Transfer reversed, %(employee)s is back in %(company)s.",
                                    employee=rec.employee_id.name, company=rec.current_company.name))
            rec._send_notification(
                'apps_employee_company_transfer.email_template_request_for_company_company_transfer_reverse_employee',
                rec.employee_id, rec.transfer_reporting_manager | rec.current_reporting_manager)
        return True

    def _target_values(self, to_target):
        """Values of the destination, either the requested ones or the snapshot to restore."""
        self.ensure_one()
        sudo = self.sudo()
        if to_target:
            return {
                'company': sudo.transfer_company, 'branch': sudo.transfer_branch,
                'department': sudo.transfer_department, 'job': sudo.transfer_job,
                'manager': sudo.transfer_reporting_manager,
                'supervisor': sudo.transfer_supervisor or sudo.current_supervisor,
                'grade': sudo.transfer_grade_id,
                'basic': sudo.transfer_employee_basic, 'housing': sudo.transfer_employee_housing_allowance,
                'travel': sudo.transfer_employee_travel_allowance, 'other': sudo.transfer_employee_other_allowance,
                'wage': sudo.transfer_employee_wage,
                'companies': sudo.employee_default_company_ids | sudo.transfer_company,
                'branches': sudo.employee_default_branch_ids | sudo.transfer_branch,
                'struct_id': sudo.struct_id, 'journal': sudo.journal_id,
            }
        return {
            'company': sudo.current_company, 'branch': sudo.current_branch,
            'department': sudo.current_department, 'job': sudo.current_job,
            'manager': sudo.current_reporting_manager, 'supervisor': sudo.current_supervisor,
            'grade': sudo.current_grade_id,
            'basic': sudo.current_employee_basic, 'housing': sudo.current_employee_housing_allowance,
            'travel': sudo.current_employee_travel_allowance, 'other': sudo.current_employee_other_allowance,
            'wage': sudo.current_employee_wage,
            'companies': sudo.employee_default_company_ids | sudo.current_company,
            'branches': sudo.employee_default_branch_ids | sudo.current_branch,
            'struct_id': sudo.employee_current_salary_structure,
            'journal': sudo.employee_current_salary_journal,
        }

    def _execute_move(self, to_target):
        """Move the employee to the target (or back to the original) company."""
        self.ensure_one()
        sudo = self.sudo()
        employee = sudo.employee_id
        source_company = sudo.transfer_company if not to_target else sudo.current_company
        target = self._target_values(to_target)
        if not employee.active:
            raise UserError(_("%s is archived and cannot be transferred.", employee.name))
        if employee.company_id != source_company:
            raise UserError(_(
                "%(employee)s is in company %(actual)s but the transfer expects %(expected)s.",
                employee=employee.name, actual=employee.company_id.name, expected=source_company.name))
        if to_target:
            effective = sudo.start_date
        else:
            today = fields.Date.context_today(self)
            effective = min(sudo.end_date or today, today)
            effective = max(effective, sudo.start_date)

        # 1. close the running contract of the employee
        self._close_running_contracts(employee, effective)
        # 2. open the new contract version (the employee is still in the source company here)
        version = self._open_contract_version(employee, effective, to_target)
        # 3. move the employee: the version level values are written on the new version
        employee.with_context(version_id=version.id).write(self._employee_vals(employee, target, to_target))
        self._complete_contract_version(version, employee, target)
        # 4. user access
        self._move_user_access(employee, target)
        # 5. time off
        if sudo.current_company != sudo.transfer_company:
            self._carry_over_leaves(employee, source_company, target['company'])

    def _employee_vals(self, employee, target, to_target):
        company = target['company']
        vals = {
            'company_id': company.id,
            'branch': target['branch'].id,
            'work_loc_id': target['branch'].id,
            'parent_id': target['manager'].id,
            'reporting_manager': target['manager'].id,
            'supervisor': target['supervisor'].id,
            'department_id': target['department'].id,
            'job_id': target['job'].id,
            'grade': target['grade'].id,
            'basic': target['basic'],
            'housing_allowance': target['housing'],
            'travel_allowance': target['travel'],
            'other_allowance': target['other'],
            'wage': target['wage'],
            'address_id': company.partner_id.id,
        }
        if to_target and self.transfer_type == 'permanent':
            vals['joining_date'] = self.start_date
        # fields checked against the company of the employee
        if employee.coach_id and employee.coach_id.company_id != company:
            vals['coach_id'] = False
        if employee.work_location_id:
            vals['work_location_id'] = False
        if employee.resource_calendar_id.company_id and employee.resource_calendar_id.company_id != company:
            vals['resource_calendar_id'] = company.resource_calendar_id.id
        return vals

    # -- contracts (hr.version) ----------------------------------------
    def _close_running_contracts(self, employee, effective):
        """End the contract running the day before the effective date."""
        day_before = effective - timedelta(days=1)
        date_from, _date_to = employee._get_contract_dates(day_before)
        if not date_from:
            return
        versions = self.env['hr.version'].sudo().search([
            ('employee_id', '=', employee.id), ('contract_date_start', '=', date_from)])
        versions.with_context(sync_contract_dates=True).write({'contract_date_end': max(day_before, date_from)})

    def _open_contract_version(self, employee, effective, to_target):
        self.ensure_one()
        end = self.end_date if (to_target and self.transfer_type == 'temp') else False
        versions = employee.version_ids
        same_day = versions.filtered(lambda v: v.date_version == effective)
        if same_day and same_day.contract_date_start and same_day.contract_date_start < effective \
                and not versions.filtered(lambda v: v.date_version < effective):
            # keep the history of the contract that is ending: the version of that day becomes the new contract
            day_before = effective - timedelta(days=1)
            employee.create_version({
                'date_version': day_before,
                'contract_date_start': same_day.contract_date_start,
                'contract_date_end': day_before,
            })
        version = employee.create_version({
            'date_version': effective,
            'contract_date_start': effective,
            'contract_date_end': end,
        }).sudo()
        if version.contract_date_start != effective or version.contract_date_end != end:
            version.with_context(sync_contract_dates=True).write({
                'contract_date_start': effective, 'contract_date_end': end})
        return version

    def _complete_contract_version(self, version, employee, target):
        self.ensure_one()
        vals = {
            'name': _('Contract for %s', employee.name),
            'additional_note': _(
                "Contract (Transfer %(name)s) for %(employee)s.\nBasic: %(basic)s, Housing: %(housing)s, "
                "Travel: %(travel)s, Other: %(other)s",
                name=self.name, employee=employee.name, basic=target['basic'], housing=target['housing'],
                travel=target['travel'], other=target['other']),
        }
        if 'struct_id' in version._fields and target.get('struct_id'):
            vals['struct_id'] = target['struct_id']
        if 'journal_id' in version._fields and target.get('journal'):
            vals['journal_id'] = target['journal'].id
        version.sudo().write(vals)

    # -- user access ----------------------------------------------------
    def _move_user_access(self, employee, target):
        user = employee.user_id
        if not user:
            return
        vals = {
            'company_ids': [(6, 0, target['companies'].ids)],
            'company_id': target['company'].id,
        }
        branches = target['branches'].filtered(lambda b: b.company_id in target['companies'])
        vals.update({'branch_ids': [(6, 0, branches.ids)], 'branch_id': target['branch'].id})
        user.write(vals)

    # -- time off -------------------------------------------------------
    def _carry_over_leaves(self, employee, from_company, to_company):
        """Carry the remaining days of the company specific time off types over the new company."""
        Allocation = self.env['hr.leave.allocation'].sudo()
        LeaveType = self.env['hr.leave.type'].sudo()
        allocations = Allocation.search([
            ('employee_id', '=', employee.id), ('state', '=', 'validate'),
            ('holiday_status_id.company_id', '=', from_company.id),
            ('holiday_status_id.requires_allocation', '=', True)])
        carried = Allocation
        for allocation in allocations:
            remaining = allocation.number_of_days - allocation.leaves_taken
            if remaining <= 0:
                continue
            new_type = LeaveType.search([
                ('company_id', '=', to_company.id), ('name', '=', allocation.holiday_status_id.name),
                ('requires_allocation', '=', True)], limit=1)
            if not new_type:
                self.message_post(body=_(
                    "No time off type '%(type)s' in %(company)s: %(days)s day(s) were not carried over.",
                    type=allocation.holiday_status_id.name, company=to_company.name, days=remaining))
                continue
            new_allocation = Allocation.create({
                'name': _('Transfer %(name)s: %(type)s', name=self.name, type=new_type.name),
                'employee_id': employee.id,
                'holiday_status_id': new_type.id,
                'number_of_days': remaining,
                'allocation_type': 'regular',
                'date_from': fields.Date.context_today(self),
            })
            new_allocation._action_validate()
            carried |= new_allocation
        if carried:
            self.sudo().write({'carried_allocation_ids': [(4, a.id) for a in carried]})
            self.message_post(body=_("%s time off allocation(s) carried over to %s.", len(carried), to_company.name))

    # ------------------------------------------------------------------
    # Smart buttons
    # ------------------------------------------------------------------
    def _action_for_employee(self, name, model, view_mode='list,form', context=None):
        self.ensure_one()
        return {
            'name': name,
            'res_model': model,
            'type': 'ir.actions.act_window',
            'view_mode': view_mode,
            'domain': [('employee_id', '=', self.employee_id.id)],
            'context': dict({'default_employee_id': self.employee_id.id, 'active_test': False}, **(context or {})),
        }

    def employee_new_contract_create_request(self):
        action = self._action_for_employee(_('Contracts'), 'hr.version')
        action['domain'] = [('employee_id', '=', self.employee_id.id), ('contract_date_start', '!=', False)]
        return action

    def employee_create_leave_request(self):
        return self._action_for_employee(_('Leave Requests'), 'hr.leave')

    def employee_new_payslip_create_request(self):
        if PAYSLIP_MODEL not in self.env:
            raise UserError(_("No payroll application is installed."))
        return self._action_for_employee(_('Payslips'), PAYSLIP_MODEL)

    def employee_leave_allocation_info(self):
        action = self._action_for_employee(_('Time Off Analysis'), 'hr.leave.report', view_mode='list')
        action['context'].pop('default_employee_id')
        return action

    def action_open_employee(self):
        self.ensure_one()
        return {
            'name': self.employee_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'res_id': self.employee_id.id,
            'view_mode': 'form',
            'context': {'active_test': False},
        }

    def action_open_moves(self):
        self.ensure_one()
        return {
            'name': _('Journal Entries'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('company_transfer_id', '=', self.id)],
            'context': {'default_company_transfer_id': self.id, 'create': False},
        }

    # ------------------------------------------------------------------
    # Payroll (optional)
    # ------------------------------------------------------------------
    def action_generate_final_payslip(self):
        """Create the draft payslip of the last period worked in the original company (payroll app only)."""
        if PAYSLIP_MODEL not in self.env:
            raise UserError(_("No payroll application is installed."))
        self._check_hr()
        self._check_state(['transfer', 'probation'], _("generate the payslip of"))
        Payslip = self.env[PAYSLIP_MODEL]
        for rec in self:
            if rec.payslip_generated:
                raise UserError(_("The final payslip of %s was already generated.", rec.employee_id.name))
            contract = rec.sudo().current_contract
            if not contract:
                raise UserError(_("%s has no contract in %s.", rec.employee_id.name, rec.current_company.name))
            date_to = rec.start_date - timedelta(days=1)
            vals = {
                'employee_id': rec.employee_id.id,
                'date_from': date_to.replace(day=1),
                'date_to': date_to,
                'company_id': rec.current_company.id,
                'name': _('Salary Slip of %(employee)s for %(period)s',
                          employee=rec.employee_id.name, period=date_to.strftime('%B %Y')),
            }
            for fname, value in (
                    ('version_id', contract.id), ('contract_id', contract.id),
                    ('struct_id', rec.employee_current_salary_structure),
                    ('journal_id', rec.employee_current_salary_journal.id)):
                if fname in Payslip._fields and value:
                    vals[fname] = value
            if 'intercompany_transfer' in Payslip._fields:
                vals['intercompany_transfer'] = True
            payslip = Payslip.sudo().create(vals)
            if hasattr(payslip, 'compute_sheet'):
                payslip.compute_sheet()
            rec.sudo().write({'payslip_generated': True})
            rec.message_post(body=_("Final payslip generated: %s", payslip.display_name))
        return True

from datetime import date
from odoo import models, fields, api, tools, _
import babel
import time
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.exceptions import Warning
from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta
from odoo.tools.float_utils import float_round


class CompanyToCompanyTransfer(models.Model):
    _name = 'company.transfer'
    _description = "Employee Company Transfer"
    _rec_name = "employee_id"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    def _default_employee(self):
        emp_ids = self.sudo().env['hr.employee'].search([('user_id', '=', self.env.uid)])
        return emp_ids and emp_ids[0] or False

    user_id = fields.Many2one('res.users', string='User', ondelete='cascade', index=True,
                              default=lambda self: self.env.user
                              )
    company_id = fields.Many2one('res.company', string='Company', ondelete='cascade', index=True,
                                 default=lambda self: self.env.company
                                 )
    name = fields.Char(string='Employee Company Transfer', required=True, copy=False, readonly=True,
                       states={'draft': [('readonly', False)]}, index=True, default=lambda self: _('New Transfer'),
                       help='A unique sequence number for the Transfer')
    remarks = fields.Text('Remarks', help="Specify notes for the transfer if any")
    requested_date = fields.Date("Requested Date", default=fields.Date.today(), help="Date")
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True,
                                  help='Select the employee you are going to transfer')
    current_company = fields.Many2one("res.company", string="Current Company")
    transfer_company = fields.Many2one("res.company",
                                       string="Transfer to Company", required=True, tracking=True)
    current_branch = fields.Many2one("res.branch", string="Current Branch")
    transfer_branch = fields.Many2one("res.branch", string="Transfer to Branch", required=True, tracking=True)
    current_department = fields.Many2one("hr.department", string="Current Department")
    transfer_department = fields.Many2one("hr.department", string="Transfer to Department", required=True,
                                          tracking=True)
    current_job = fields.Many2one("hr.job", string="Current Designation")
    transfer_job = fields.Many2one("hr.job", string="Transfer to Designation", required=True, tracking=True)
    current_reporting_manager = fields.Many2one("hr.employee", string="Reporting Manager", required=True)
    transfer_reporting_manager = fields.Many2one("hr.employee", string="Transfer to Reporting Manager", required=True,
                                                 tracking=True)
    current_supervisor = fields.Many2one("hr.employee", string="Supervisor", required=True)
    transfer_supervisor = fields.Many2one("hr.employee", string="Transfer to Supervisor", tracking=True)
    current_contract = fields.Many2one("hr.contract", string="Current Contract")
    current_employee_remaining_leaves = fields.Integer(string='Remaining Time Off')
    current_leave = fields.Many2one("hr.employee", string="Current Leave")
    current_allocation_used_count = fields.Many2one("hr.leave", string="Current Leave Used")
    current_allocation_count = fields.Many2one("hr.leave", string="Current Leave Count")
    current_employee_leave = fields.Integer(string='Leave', invisible=True)
    current_employee_basic = fields.Float(string='Basic')
    current_employee_housing_allowance = fields.Float(string='House Allowance')
    current_employee_travel_allowance = fields.Float(string='Travel Allowance')
    current_employee_other_allowance = fields.Float(string='Other Allowance')
    current_employee_wage = fields.Float(string='Wage')

    transfer_employee_basic = fields.Float(string='Basic', tracking=True)
    transfer_employee_housing_allowance = fields.Float(string='House Allowance', tracking=True)
    transfer_employee_travel_allowance = fields.Float(string='Travel Allowance', tracking=True)
    transfer_employee_other_allowance = fields.Float(string='Other Allowance', tracking=True)
    transfer_employee_wage = fields.Float(string='Wage', tracking=True)

    employee_current_salary_structure = fields.Many2one('hr.payroll.structure', string='Current Structure')
    employee_current_contract = fields.Many2one('hr.contract', string='Current Contract')
    employee_current_salary_journal = fields.Many2one('account.journal', string='Current Journal')
    leave_department_id = fields.Many2one("hr.leave.report", string='Leave Department')
    current_grade_id = fields.Many2one("employee.grade", string="Current Grade")
    transfer_grade_id = fields.Many2one("employee.grade", string="Transfer Grade", required=True)
    leave_employee_leave_type = fields.Many2one("hr.leave.report", string='Employee Leave Type')
    number_of_days = fields.Integer(string='Number of Days', compute='compute_employee_remaining_leaves')
    allocated_days = fields.Integer(string='Leave Allocation', compute='compute_employee_remaining_leaves')
    struct_id = fields.Many2one('hr.payroll.structure', string='Structure', required=True)
    journal_id = fields.Many2one('account.journal', string="Salary Journal", required=True,
                                 domain=[('journal_id.type', 'not in', 'sale', 'purchase')])
    employee_default_company = fields.Many2one("res.company", string="Default Company")
    employee_default_company_ids = fields.Many2many('res.company', string='Default Allowed Companies')
    employee_default_branch = fields.Many2one("res.branch", string="Default Branch")
    employee_default_branch_ids = fields.Many2many('res.branch', string='Default Allowed Branches')
    employee_holiday_status_id = fields.Many2one("hr.leave.type", string="Leave Type")
    leave_id = fields.Many2one('hr.leave', 'Employee leave', domain="[('employee_id', '=', employee_id)]")
    state = fields.Selection(
        [('draft', 'Draft'),
         ('cancel', 'Cancelled'),
         ('submit', 'Waiting for Reporting Manager Approval'),
         ('reverse_approve', 'Waiting for Reporting Manager Approval'),
         ('approve', 'Approved'),
         ('reverse', 'Reversed'),
         ('reject', 'Reject'),
         ('probation', 'Request for Probation Approval'),
         ('transfer', 'Transferred')],
        string='Status', readonly=True, copy=False, default='draft',
        help=" * The 'Draft' status is used when a transfer is created and unconfirmed Transfer.\n"
             "* The 'Transferred' status is used when the user confirm the transfer, and Cancelled old contract of "
             "employee.\n"
             " * The 'Cancelled' status is used when user cancel Transfer.")
    start_date = fields.Date("Start Date")
    end_date = fields.Date("End Date")
    transfer_type = fields.Selection(
        [('temp', 'Temporary'),
         ('permanent', 'Permanent')],
        string='Transfer Type')
    record_type = fields.Selection([('inter', 'INTER'), ('intra', 'INTRA')])
    responsible = fields.Many2one('hr.employee', string='Requested By', default=_default_employee, readonly=True,
                                  help="Responsible person for the transfer")
    employee_count = fields.Integer(compute='_compute_employee_count')
    employee_contract_count = fields.Integer(compute='_compute_employee_contract_count', string='Contract',
                                             default=0)
    employee_payslip_count = fields.Integer(compute='_compute_employee_payslip_count', string='Payslip',
                                            default=0)

    employee_gratuity_count = fields.Integer(compute='_compute_employee_gratity_count', string='Gratuity',
                                             default=0)
    employee_notice_period = fields.Integer(compute='compute_employee_notice_period_button', string='/ Days',
                                            default=0)
    employee_leave_request = fields.Integer(compute='_compute_employee_leave_request', string='Leave Request',
                                            default=0)
    gratuity_amount = fields.Float("Gratuity Amount")
    image_field = fields.Binary(string="image")

    # @api.onchange('record_type', 'employee_id')
    # def _onchange_record_type(self):
    #     self.transfer_company = self.current_company.id
    #     print('-============-========-----------------------', self.current_company)

    @api.onchange('employee_id')
    def onchange_employee_id(self):
        if self.employee_id:
            self.sudo().write({
                'current_company': self.employee_id.company_id.id,
                'current_branch': self.employee_id.branch.id,
                'employee_default_company': self.employee_id.user_id.company_id.id,
                'employee_default_company_ids': self.employee_id.user_id.company_ids.ids,
                'employee_current_contract': self.employee_id.current_contract.id,
                'employee_current_salary_structure': self.employee_id.current_contract.struct_id.id,
                'employee_current_salary_journal': self.employee_id.current_contract.journal_id.id,
                'current_department': self.employee_id.department_id.id,
                'current_job': self.employee_id.job_id.id,
                'current_reporting_manager': self.employee_id.reporting_manager.id,
                'current_supervisor': self.employee_id.supervisor.id,
                'current_grade_id': self.employee_id.grade.id,
                'employee_default_branch': self.employee_id.user_id.branch_id.id,
                'employee_default_branch_ids': self.employee_id.user_id.branch_ids.ids,
                'current_contract': self.employee_id.current_contract.id,
                'current_employee_remaining_leaves': self.employee_id.remaining_leaves,
                # 'current_allocation_used_count': self.employee_id.allocation_used_count,
                'current_allocation_count': self.employee_id.allocation_count,
                # 'current_employee_leave': self.employee_id.employee_leave,
                'current_employee_basic': self.employee_id.basic,
                'current_employee_housing_allowance': self.employee_id.housing_allowance,
                'current_employee_travel_allowance': self.employee_id.travel_allowance,
                'current_employee_other_allowance': self.employee_id.other_allowance,
                'current_employee_wage': self.employee_id.wage,
                'transfer_employee_basic': self.employee_id.basic,
                'transfer_employee_housing_allowance': self.employee_id.housing_allowance,
                'transfer_employee_travel_allowance': self.employee_id.travel_allowance,
                'transfer_employee_other_allowance': self.employee_id.other_allowance,
                'transfer_employee_wage': self.employee_id.wage,
                'image_field': self.employee_id.image_1920,
            })
            if self.record_type == 'intra':
                self.transfer_company = self.employee_id.company_id.id,
            # self.sudo().get_eligible_amount1()

    def submit_employee_company_transfer(self):
        camel_case = (dict(self._fields['record_type'].selection).get(
            self.record_type)).title()
        if self.record_type == 'inter':
            if self.current_company == self.transfer_company:
                raise ValidationError(
                    "Alert!!, Current Company and Transferred Company cannot be same for %s." % self.employee_id.name)
        hr_employee = self.sudo().env['hr.employee'].sudo().search([('id', '=', self.employee_id.id)])
        ctx = self.sudo().env.context.copy()
        current_user = self.env.user.name
        current_url = self.sudo().env['ir.config_parameter'].sudo().get_param('web.base.url')
        current_url += '/web#id=%d&view_type=form&model=%s' % (self.id, self._name)
        email_values = {
            # 'name': self.name,
            # 'employee': self.employee_id.name,
            # 'url': current_url,
            # 'current_user': current_user,
            # 'current_company': self.sudo().current_company.name,
            # 'current_reporting_manager': self.sudo().current_reporting_manager.name,
            # 'date': self.requested_date,
            # 'transferred_reporting_manager': self.sudo().transfer_reporting_manager.name,
            # 'reverse_reporting_manager': self.sudo().current_reporting_manager.name,

            'subject': (dict(self._fields['record_type'].selection).get(
                self.record_type)) + " COMPANY APPROVAL NOTIFICATION",
            'email_from': self.env.user.email_formatted,
            'email_to': self.sudo().current_reporting_manager.work_email,
            'email_cc': '',
        }
        template = self.sudo().env.ref(
            'apps_employee_company_transfer.email_template_request_for_company_company_transfer_submit_new', False)
        template.with_context(url=current_url, line=camel_case).send_mail(self.id, force_send=True,
                                                                          email_values=email_values)
        self.sudo().write({'state': 'submit'})

    # THIS FUNCTIONALITY HELPS USERS TO FIND THE EMPLOYEE'S REMAINING LEAVES'
    def compute_employee_remaining_leaves(self):
        for leave in self:
            domain = [
                ('employee_id', '=', leave.employee_id.id),
            ]
            total_leave_consumed = 0.0
            total_leave_alloted = 0.0
            timeoff = leave.env['hr.leave.report'].search(domain)
            for time in timeoff:
                if time.leave_type == 'allocation':
                    total_leave_consumed += time.number_of_days
                if time.leave_type == 'request':
                    total_leave_alloted += time.number_of_days
            leave.number_of_days = total_leave_consumed
            leave.allocated_days = abs(total_leave_alloted)

    def approve_employee_company_transfer(self):
        camel_case = (dict(self._fields['record_type'].selection).get(
            self.record_type)).title()
        if (self.env.user.id == self.sudo().current_reporting_manager.user_id.id or \
                self.sudo().env.user.has_group('hr.group_hr_manager') or
                self.sudo().env.user.has_group('hr.group_hr_user')):
            ctx = self.sudo().env.context.copy()
            current_user = self.env.user.name
            current_url = self.sudo().env['ir.config_parameter'].sudo().get_param('web.base.url')
            current_url += '/web#id=%d&view_type=form&model=%s' % (self.id, self._name)
            email_values = {
                # 'name': self.name,
                # 'employee': self.employee_id.name,
                # 'url': current_url,
                # 'current_user': current_user,
                # 'current_company': self.sudo().current_company.name,
                # 'transfer_company': self.sudo().transfer_company.name,
                # 'current_reporting_manager': self.sudo().current_reporting_manager.name,
                # 'transferred_reporting_manager': self.sudo().transfer_reporting_manager.name,
                # 'date': self.requested_date,
                'subject': "EMPLOYEE " + (dict(self._fields['record_type'].selection).get(
                    self.record_type)) + " COMPANY APPROVED NOTIFICATION",
                'email_from': self.env.user.email_formatted,
                'email_to': self.employee_id.work_email,
                'email_cc': self.transfer_reporting_manager.work_email,
            }

            template = self.sudo().env.ref(
                'apps_employee_company_transfer.email_template_request_for_company_company_transfer_approved', False)
            template.with_context(url=current_url, line=camel_case).send_mail(self.id, force_send=True,
                                                                              email_values=email_values)

            # template = self.sudo().env.ref(
            #     'hr_employee_orientation.email_template_request_for_company_company_transfer_approved',
            #     False)
            # template.with_context(ctx).sudo().send_mail(self.id, force_send=True)
            self.sudo().write({'state': 'approve'})
        else:
            raise UserError(_(
                "Alert !! You are not allowed to approve the Inter Company Transfer.\n"
                "Only, Reporting Manager allowed to Approve it.\n"))

    def reject_employee_company_transfer(self):
        camel_case = (dict(self._fields['record_type'].selection).get(
            self.record_type)).title()
        if (self.env.user.id == self.sudo().current_reporting_manager.user_id.id or \
                self.sudo().env.user.has_group('hr.group_hr_manager') or
                self.sudo().env.user.has_group('hr.group_hr_user')):
            ctx = self.sudo().env.context.copy()
            current_user = self.env.user.name
            current_url = self.sudo().env['ir.config_parameter'].sudo().get_param('web.base.url')
            current_url += '/web#id=%d&view_type=form&model=%s' % (self.id, self._name)
            email_values = {
                # 'name': self.name,
                # 'employee': self.employee_id.name,
                # 'url': current_url,
                # 'current_user': current_user,
                # 'current_company': self.sudo().current_company.name,
                # 'current_reporting_manager': self.sudo().current_reporting_manager.name,
                # 'date': self.requested_date,
                'subject': "EMPLOYEE " + (dict(self._fields['record_type'].selection).get(
                    self.record_type)) + " COMPANY REJECTED NOTIFICATION",
                'email_from': self.env.user.email_formatted,

                'email_to': self.employee_id.work_email,
                'email_cc': self.transfer_reporting_manager.work_email,
            }
            template = self.sudo().env.ref(
                'apps_employee_company_transfer.email_template_request_for_company_company_transfer_rejected', False)
            template.with_context(url=current_url, line=camel_case).send_mail(self.id, force_send=True,
                                                                              email_values=email_values)

            self.sudo().write({'state': 'reject'})
        else:
            raise UserError(_(
                "Alert !! You are not allowed to reject the Inter Company Transfer.\n"
                "Only, Reporting Manager allowed to Reject it.\n"))

    def set_to_draft(self):
        self.sudo().write({'state': 'draft'})

    def cancel_employee_company_transfer(self):
        camel_case = (dict(self._fields['record_type'].selection).get(
            self.record_type)).title()
        ctx = self.sudo().env.context.copy()
        current_user = self.env.user.name
        current_url = self.sudo().env['ir.config_parameter'].sudo().get_param('web.base.url')
        current_url += '/web#id=%d&view_type=form&model=%s' % (self.id, self._name)
        email_values = {
            # 'name': self.name,
            # 'employee': self.sudo().employee_id.name,
            # 'url': current_url,
            # 'current_user': current_user,
            # 'current_company': self.sudo().current_company.name,
            # 'current_reporting_manager': self.sudo().current_reporting_manager.name,
            # 'date': self.requested_date,
            'subject': "EMPLOYEE " + (dict(self._fields['record_type'].selection).get(
                self.record_type)) + " COMPANY CANCELLED NOTIFICATION",
            'email_from': self.env.user.email_formatted,

            'email_to': self.sudo().employee_id.work_email,
            'email_cc': self.sudo().transfer_reporting_manager.work_email,
        }
        template = self.sudo().env.ref(
            'apps_employee_company_transfer.email_template_request_for_company_company_transfer_cancelled', False)
        template.with_context(url=current_url, line=camel_case).send_mail(self.id, force_send=True,
                                                                          email_values=email_values)
        self.sudo().write({'state': 'cancel'})

    def employee_probation_notify(self):
        if self.state == 'transfer' and self.employee_notice_period == 1:
            self.sudo().write({'state': 'probation'})
        else:
            self.employee_notice_period = 0
        ctx = self.sudo().env.context.copy()
        current_user = self.env.user.name
        current_url = self.sudo().env['ir.config_parameter'].sudo().get_param('web.base.url')
        current_url += '/web#id=%d&view_type=form&model=%s' % (self.id, self._name)
        ctx.update({
            'name': self.name,
            'employee': self.employee_id.name,
            'url': current_url,
            'current_user': current_user,
            'current_company': self.current_company.name,
            'transfer_company': self.transfer_company.name,
            'current_reporting_manager': self.current_reporting_manager.name,
            'transferred_reporting_manager': self.transfer_reporting_manager.name,
            'employee_notice_period': self.employee_notice_period,
            'date': self.requested_date,
            'email_to': self.employee_id.work_email,
            'email_cc': self.transfer_reporting_manager.work_email,
        })
        # template = self.sudo().env.ref(
        #     'hr_employee_orientation.email_template_request_for_company_company_transfer_reverse',
        #     False)
        # template.with_context(ctx).sudo().send_mail(self.id, force_send=True)

    def reverse_new_transfer_payslip(self):
        ttyme = datetime.fromtimestamp(time.mktime(time.strptime(str(self.requested_date), "%Y-%m-%d")))
        locale = self.sudo().env.context.get('lang') or 'en_US'
        if self.transfer_type == 'temp':
            ttyme = datetime.fromtimestamp(time.mktime(time.strptime(str(self.requested_date), "%Y-%m-%d")))
            locale = self.sudo().env.context.get('lang') or 'en_US'
            # print("ffsdfdsfsd",self.start_date.strftime('%d'))
            # err
            if self.end_date.strftime('%d') == '01':
                self.payslip_reverse_generated = True
                pass
                # first_date=self.start_date - timedelta(days=1)
                # payslip = self.env['hr.payslip'].sudo().create({
                #     'employee_id': self.employee_id.id,
                #     'name': _('Salary Slip of %s for %s') % (self.employee_id.name, tools.ustr(babel.dates.format_date(date=ttyme, format='MMMM-y', locale=locale))),
                #     'number': 'Contract for ' + str(self.employee_id.name),
                #     'date_to': self.start_date - timedelta(days=1),
                #     'date': self.requested_date,
                #     'company_id': self.current_company.id,
                #     'branch_id': self.current_branch.id,
                #     'contract_id': self.employee_current_contract.id,
                #     # 'journal_id': self.employee_current_salary_journal.id,
                #     'struct_id': self.employee_current_salary_structure.id,
                #     'date_from':first_date.replace(day=1),
                #     'intercompany_transfer':True,
                # })
                # payslip.onchange_employee()
                # payslip.compute_sheet()
                # print("DDDDDDDDDDDDDDDDDDDDDDDVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV",self.start_date.strftime('%d'))

            else:
                hr_contract = self.env['hr.contract'].sudo().search(
                    [('employee_id', '=', self.employee_id.id), ('company_id', '=', self.transfer_company.id)], limit=1)
                payslip = self.env['hr.payslip'].sudo().create({
                    'employee_id': self.employee_id.id,
                    'name': _('Salary Slip of %s for %s') % (self.employee_id.name, tools.ustr(
                        babel.dates.format_date(date=ttyme, format='MMMM-y', locale=locale))),
                    'number': 'Contract for ' + str(self.employee_id.name),
                    'date_to': self.end_date - timedelta(days=1),
                    'date': self.requested_date,
                    'company_id': self.transfer_company.id,
                    'branch_id': self.transfer_branch.id,
                    'contract_id': hr_contract.id,
                    'journal_id': self.employee_current_salary_journal.id,
                    'struct_id': self.struct_id.id,
                    'date_from': self.end_date.replace(day=1),
                    'intercompany_transfer': True,
                })
                payslip.onchange_employee()
                payslip.compute_sheet()
                self.payslip_reverse_generated = True

            return payslip

    def reverse_employee_company_transfer(self):
        camel_case = (dict(self._fields['record_type'].selection).get(
            self.record_type)).title()
        hr_employee = self.sudo().env['hr.employee'].sudo().search([('id', '=', self.employee_id.id)])
        self.sudo().cancel_transfer()
        self.sudo().reverse_new_transfer_contract()
        # self.sudo().create_leave_current_company_allocation()
        # self.sudo().cancel_transfered_company_create_leave_allocation()
        # self.sudo().reverse_new_transfer_payslip()
        hr_employee.sudo().write({'company_id': self.current_company.id,
                                  # 'wps_company': self.current_company.id,
                                  'branch_id': self.current_branch.id,
                                  # 'work_loc_id': self.current_branch.id,
                                  'parent_id': self.current_reporting_manager.id,
                                  'department_id': self.current_department.id,
                                  # 'job_id': self.current_job.id,
                                  'grade': self.current_grade_id.id,
                                  'address_id': self.current_company.id
                                  })
        if int(self.current_grade_id.grade):
            hr_employee.sudo().write({
                'supervisor': self.current_supervisor.id})
        employee_id = self.env['res.users'].sudo().search([('id', '=', self.employee_id.user_id.id)])
        if employee_id and self.transfer_branch:
            company = self.employee_id.user_id.company_ids.ids
            branch = self.employee_id.user_id.branch_ids.ids
            employee_company = self.current_company.id
            employee_branch = self.current_branch.id
            company.append(employee_company)
            branch.append(employee_branch)
            employee_id.sudo().write({
                'company_id': self.current_company.id,
                'company_ids': company,
                'branch_ids': branch,
                'branch_id': self.current_branch.id,
            })
        self.state = 'reverse'
        ctx = self.sudo().env.context.copy()
        current_user = self.env.user.name
        current_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        current_url += '/web#id=%d&view_type=form&model=%s' % (self.id, self._name)
        email_values = {
            # 'name': self.name,
            # 'employee': self.employee_id.name,
            # 'url': current_url,
            # 'current_user': current_user,
            # 'transfer_company': self.transfer_company.name,
            # 'reverse_company': self.current_company.name,
            # 'transferred_reporting_manager': self.transfer_reporting_manager.name,
            # 'reverse_reporting_manager': self.current_reporting_manager.name,
            # 'date': self.requested_date,
            'subject': "EMPLOYEE " + (dict(self._fields['record_type'].selection).get(
                self.record_type)) + " COMPANY CANCELLED NOTIFICATION",
            'email_from': self.env.user.email_formatted,

            'email_to': self.employee_id.work_email,
            'email_cc': self.transfer_reporting_manager.work_email,
        }
        template = self.sudo().env.ref(
            'apps_employee_company_transfer.email_template_request_for_company_company_transfer_reverse_employee',
            False)
        template.with_context(url=current_url, line=camel_case).send_mail(self.id, force_send=True,
                                                                          email_values=email_values)

    def update_employee_company_transfer(self):
        camel_case = (dict(self._fields['record_type'].selection).get(
            self.record_type)).title()
        if self.sudo().env.user.has_group('hr.group_hr_manager') or self.sudo().env.user.has_group('hr.group_hr_user'):
            hr_employee = self.env['hr.employee'].sudo().search([('id', '=', self.employee_id.id)])

            if self.record_type == 'inter':
                if self.current_company == self.transfer_company:
                    raise ValidationError(
                        "Alert!!, Current Company and Transferred Company cannot be same for %s." % self.employee_id.name)
                if self.transfer_type == 'permanent':
                    self.sudo().create_graduity()
                    self.sudo().cancel_transfer()
                    self.sudo().create_new_transfer_contract()
                    # self.sudo().create_new_transfer_payslip()
                    hr_employee.sudo().write({
                        'company_id': self.transfer_company.id,
                        'branch_id': self.transfer_branch.id,
                        'work_loc_id': self.transfer_branch.id,
                        'parent_id': self.transfer_reporting_manager.id,
                        'department_id': self.transfer_department.id,
                        'job_id': self.transfer_job.id,
                        'grade': self.transfer_grade_id.id,
                        'joining_date': self.requested_date,
                        'address_id': self.transfer_company.id,
                        'supervisor': self.transfer_supervisor.id,
                        'reporting_manager': self.transfer_reporting_manager,
                    })
                if int(self.current_grade_id.grade) <= 2 and self.transfer_supervisor:
                    hr_employee.sudo().write({
                        'supervisor': self.transfer_supervisor.id})
                if int(self.current_grade_id.grade) <= 2 and not self.transfer_supervisor:
                    hr_employee.sudo().write({
                        'supervisor': self.current_supervisor.id})

                employee_id = self.env['res.users'].sudo().search([('id', '=', self.employee_id.user_id.id)])
                if employee_id and self.transfer_branch:
                    company = self.employee_id.user_id.company_ids.ids
                    branch = self.employee_id.user_id.branch_ids.ids
                    employee_company = self.transfer_company.id
                    employee_branch = self.transfer_branch.id
                    company.append(employee_company)
                    branch.append(employee_branch)
                    employee_id.sudo().write({
                        'company_id': self.transfer_company.id,
                        'company_ids': company,
                        'branch_ids': branch,
                        'branch_id': self.transfer_branch.id,
                    })
                # self.state = 'transfer'
                print("66666666666666")

            else:
                print("555555555555555555555")
                self.sudo().cancel_transfer()
                self.sudo().create_new_transfer_contract()
                # self.sudo().create_new_transfer_payslip()
                hr_employee.sudo().write({
                    'company_id': self.transfer_company.id,
                    'branch_id': self.transfer_branch.id,
                    'work_loc_id': self.transfer_branch.id,
                    'parent_id': self.transfer_reporting_manager.id,
                    'department_id': self.transfer_department.id,
                    'job_id': self.transfer_job.id,
                    'grade': self.transfer_grade_id.id,
                    'joining_date': self.requested_date,
                    'address_id': self.transfer_company.id,
                    'supervisor': self.transfer_supervisor.id,
                    'reporting_manager': self.transfer_reporting_manager,
                })
            if int(self.current_grade_id.grade) <= 2 and self.transfer_supervisor:
                hr_employee.sudo().write({
                    'supervisor': self.transfer_supervisor.id})
            if int(self.current_grade_id.grade) <= 2 and not self.transfer_supervisor:
                hr_employee.sudo().write({
                    'supervisor': self.current_supervisor.id})

            employee_id = self.env['res.users'].sudo().search([('id', '=', self.employee_id.user_id.id)])
            if employee_id and self.transfer_branch:
                company = self.employee_id.user_id.company_ids.ids
                branch = self.employee_id.user_id.branch_ids.ids
                employee_company = self.transfer_company.id
                employee_branch = self.transfer_branch.id
                company.append(employee_company)
                branch.append(employee_branch)
                employee_id.sudo().write({
                    'company_id': self.transfer_company.id,
                    'company_ids': company,
                    'branch_ids': branch,
                    'branch_id': self.transfer_branch.id,
                })
            # self.state = 'transfer'

            if self.transfer_type == 'permanent':
                self.sudo().create_graduity()

            else:
                self.sudo().cancel_transfer()
                self.sudo().create_new_transfer_contract()
                # self.sudo().create_new_transfer_payslip()
                hr_employee.sudo().write({
                    'company_id': self.transfer_company.id,
                    'branch_id': self.transfer_branch.id,
                    'work_loc_id': self.transfer_branch.id,
                    'parent_id': self.transfer_reporting_manager.id,
                    'department_id': self.transfer_department.id,
                    'job_id': self.transfer_job.id,
                    'grade': self.transfer_grade_id.id,
                    'joining_date': self.requested_date,
                    'address_id': self.transfer_company.id,
                    'supervisor': self.transfer_supervisor.id,
                    'reporting_manager': self.transfer_reporting_manager,
                })
            if int(self.current_grade_id.grade) <= 2 and self.transfer_supervisor:
                hr_employee.sudo().write({
                    'supervisor': self.transfer_supervisor.id})
            if int(self.current_grade_id.grade) <= 2 and not self.transfer_supervisor:
                hr_employee.sudo().write({
                    'supervisor': self.current_supervisor.id})

            employee_id = self.env['res.users'].sudo().search([('id', '=', self.employee_id.user_id.id)])
            if employee_id and self.transfer_branch:
                company = self.employee_id.user_id.company_ids.ids
                branch = self.employee_id.user_id.branch_ids.ids
                employee_company = self.transfer_company.id
                employee_branch = self.transfer_branch.id
                company.append(employee_company)
                branch.append(employee_branch)
                employee_id.sudo().write({
                    'company_id': self.transfer_company.id,
                    'company_ids': company,
                    'branch_ids': branch,
                    'branch_id': self.transfer_branch.id,
                })
            # self.state = 'transfer'
            # allocated = self.create_leave_allocation()
            # allocated.action_confirm()
            # self.sudo().cancel_create_leave_allocation()

            ctx = self.sudo().env.context.copy()
            current_user = self.env.user.name
            current_url = self.sudo().env['ir.config_parameter'].sudo().get_param('web.base.url')
            current_url += '/web#id=%d&view_type=form&model=%s' % (self.id, self._name)
            email_values = {
                # 'name': self.name,
                # 'employee': self.employee_id.name,
                # 'url': current_url,
                # 'current_user': current_user,
                # 'current_company': self.sudo().current_company.name,
                # 'transfer_company': self.sudo().transfer_company.name,
                # 'current_reporting_manager': self.sudo().current_reporting_manager.name,
                # 'transferred_reporting_manager': self.sudo().transfer_reporting_manager.name,
                # 'date': self.requested_date,
                'subject': "EMPLOYEE " + (dict(self._fields['record_type'].selection).get(
                    self.record_type)) + " COMPANY TRANSFERED NOTIFICATION",
                'email_from': self.env.user.email_formatted,

                'email_to': self.get_previous_transfer_reporting_manager(),
                'email_cc': self.employee_id.work_email,
            }

            template = self.sudo().env.ref(
                'apps_employee_company_transfer.email_template_request_for_company_company_transfer_approved', False)
            template.with_context(url=current_url, line=camel_case).send_mail(self.id, force_send=True,
                                                                              email_values=email_values)

        else:
            raise ValidationError(
                "Alert !! You are not allowed to Transfer.")

    def create_graduity(self):
        if not self.current_company.journal_id:
            raise ValidationError("Please select the journal for the company %s" % (self.current_company.name))
        if not self.current_company.gratuity_debit_account_id or not self.current_company.gratuity_credit_account_id:
            raise ValidationError(
                "Please select the Gratuity debit account and Gratuity credit account for the company %s" % (
                    self.current_company.name))

        if not self.transfer_company.journal_id:
            raise ValidationError("Please select the journal for the company %s" % (self.transfer_company.name))
        if not self.transfer_company.gratuity_debit_account_id or not self.transfer_company.gratuity_credit_account_id:
            raise ValidationError(
                "Please select the Gratuity debit account and Gratuity credit account for the company %s" % (
                    self.transfer_company.name))
        move_ids = []
        transfer_move_ids = []
        account_move = {'journal_id': self.sudo().current_company.journal_id.id, 'company_transfer_id': self.id,
                        'branch_id': self.sudo().current_branch.id, 'ref': self.name}
        move = self.env['account.move'].sudo().create(account_move)
        current_company_account_line = {
            'move_id': move.id,
            'name': 'Ref: ' + str(self.employee_id.name),
            'debit': self.gratuity_amount,
            'credit': 0,
            # 'date_maturity': line.counter_part_move_id.date,
            'partner_id': self.sudo().employee_id.user_id.partner_id.id,
            'account_id': self.sudo().current_company.gratuity_debit_account_id.id,
        }
        current_company_account_line2 = {
            'move_id': move.id,
            'name': 'Ref: ' + str(self.employee_id.name),
            'debit': 0,
            'credit': self.gratuity_amount,
            # 'date_maturity': line.counter_part_move_id.date,
            'partner_id': self.sudo().employee_id.user_id.partner_id.id,
            'account_id': self.sudo().current_company.gratuity_credit_account_id.id,
        }
        move_ids.append((0, 0, current_company_account_line))
        move_ids.append((0, 0, current_company_account_line2))
        move.line_ids = move_ids
        move.sudo().action_post()

        # Transfer Company
        transfer_account_move = {'journal_id': self.sudo().transfer_company.journal_id.id,
                                 'company_transfer_id': self.id, 'branch_id': self.sudo().transfer_branch.id,
                                 'ref': self.name}
        transfer_move = self.env['account.move'].sudo().create(transfer_account_move)
        transfer_company_account_line = {
            'move_id': transfer_move.id,
            'name': 'Ref: ' + str(self.employee_id.name),
            'debit': self.gratuity_amount,
            'credit': 0,
            # 'date_maturity': line.counter_part_move_id.date,
            'partner_id': self.sudo().employee_id.user_id.partner_id.id,
            'account_id': self.sudo().transfer_company.gratuity_debit_account_id.id,
        }
        transfer_company_account_line2 = {
            'move_id': transfer_move.id,
            'name': 'Ref: ' + str(self.employee_id.name),
            'debit': 0,
            'credit': self.gratuity_amount,
            # 'date_maturity': line.counter_part_move_id.date,
            'partner_id': self.sudo().employee_id.user_id.partner_id.id,
            'account_id': self.sudo().transfer_company.gratuity_credit_account_id.id,
        }
        transfer_move_ids.append((0, 0, transfer_company_account_line))
        transfer_move_ids.append((0, 0, transfer_company_account_line2))
        transfer_move.line_ids = transfer_move_ids
        transfer_move.sudo().action_post()

    def employee_new_contract_create_request(self):
        self.sudo().ensure_one()
        context = dict(self._context or {})
        active_model = context.get('active_model')
        form_view = self.sudo().env.ref('hr_contract.hr_contract_view_form')
        tree_view = self.sudo().env.ref('hr_contract.hr_contract_view_tree')
        return {
            'name': _('Contract'),
            'res_model': 'hr.contract',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'views': [(tree_view.id, 'tree'), (form_view.id, 'form')],
            'domain': [('employee_id', '=', self.employee_id.id)],
        }

    @api.onchange('start_date')
    def onchange_start_date(self):
        if self.start_date and self.employee_id:
            pass
            # self.get_eligible_amount1()

    @api.depends('start_date')
    # def get_eligible_amount1(self):
    #     eos_type = 'resignation'
    #     # if not self.start_date:
    #     #     raise ValidationError("Please select the date..!")
    #     if self.employee_id:
    #         if not self.employee_id.joining_date:
    #             raise ValidationError(_('Employee joining date missing.Please Check and Confirm..!'))
    #
    #         if self.employee_id.grade.contract_type == 'current':
    #             contract = self.env['hr.contract'].sudo().search(
    #                 [('employee_id', '=', self.employee_id.id), ('state', '=', 'open')],
    #                 limit=1)
    #         else:
    #             contract = self.env['hr.contract'].sudo().search(
    #                 [('employee_id', '=', self.employee_id.id)], order="id",
    #                 limit=1)
    #         if not contract:
    #             raise ValidationError(_('No contract found for this employee..!Please check and confirm.'))
    #
    #         # self.eos_line = None
    #         basic = contract.basic
    #         total_service = (self.start_date - self.employee_id.joining_date).days + 1
    #         total_years = total_service / 365
    #
    #         if contract:
    #             eosb_days = 0.0
    #             eosb_list = []
    #             if contract.cont_type == 'limited':
    #                 if 0 < total_years <= 4:
    #                     eosb_days = 0
    #                     diff = (self.start_date - self.employee_id.joining_date).days + 1
    #                     eosb_list.append(
    #
    #                         ((contract.basic / 30) * eosb_days * diff / 365)
    #                     )
    #
    #                 if 4 < total_years < 5:
    #                     eosb_days = 14
    #                     diff = (self.start_date - self.employee_id.joining_date).days + 1
    #                     eosb_list.append(
    #
    #                         ((contract.basic / 30) * eosb_days * diff / 365)
    #                     )
    #
    #                 if total_years >= 5:
    #                     eosb_days = 21
    #                     diff = (self.employee_id.joining_date + relativedelta(years=5,
    #                                                                           days=-1) - self.employee_id.joining_date).days + 1
    #                     eosb_list.append(
    #
    #                         ((contract.basic / 30) * eosb_days * diff / 365)
    #                     )
    #
    #                     eosb_days1 = 30
    #                     from_date1 = self.employee_id.joining_date + relativedelta(years=5)
    #                     to_date1 = self.start_date
    #                     diff1 = (to_date1 - from_date1).days + 1
    #                     eosb_list.append(
    #
    #                         (diff1 / 365 * contract.basic)
    #                     )
    #             elif contract.cont_type == 'un_limited':
    #                 if 0 < total_years <= 1:
    #                     eosb_days = 0
    #                     diff = (self.start_date - self.sudo().employee_id.joining_date).days + 1
    #                     eosb_list.append(
    #
    #                         ((contract.basic / 30) * eosb_days * diff / 365)
    #                     )
    #                 if 1 < total_years <= 3:
    #                     eosb_days = 7
    #                     diff = (self.start_date - self.sudo().employee_id.joining_date).days + 1
    #                     eosb_list.append(
    #
    #                         ((contract.basic / 30) * eosb_days * diff / 365)
    #                     )
    #
    #                 if 3 < total_years < 5:
    #                     eosb_days = 14
    #                     diff = (self.start_date - self.sudo().employee_id.joining_date).days + 1
    #                     eosb_list.append(
    #
    #                         ((contract.basic / 30) * eosb_days * diff / 365)
    #                     )
    #
    #                 if total_years >= 5:
    #                     eosb_days = 21
    #                     diff = (self.employee_id.joining_date + relativedelta(years=5,
    #                                                                           days=-1) - self.sudo().employee_id.joining_date).days + 1
    #                     eosb_list.append(
    #
    #                         ((contract.basic / 30) * eosb_days * diff / 365))
    #
    #                     eosb_days1 = 30
    #                     from_date1 = self.employee_id.joining_date + relativedelta(years=5)
    #                     to_date1 = self.start_date
    #                     diff1 = (to_date1 - from_date1).days + 1
    #                     eosb_list.append(
    #                         (diff1 / 365 * contract.basic)
    #                     )
    #         self.gratuity_amount = sum(eosb_list)

    def employee_create_leave_request(self):
        self.sudo().ensure_one()
        context = dict(self._context or {})
        active_model = context.get('active_model')
        form_view = self.sudo().env.ref('hr_holidays.hr_leave_view_form')
        tree_view = self.sudo().env.ref('hr_holidays.hr_leave_view_tree_my')
        for this in self:
            if this._context is None:
                context = {}
            partner = {}
            for m in this:
                partner = {
                    'name': m.employee_id.name,
                    'company_id': m.transfer_department.id,
                }

            return {
                'name': _('Leave Request'),
                'res_model': 'hr.leave',
                'type': 'ir.actions.act_window',
                'view_mode': 'tree,form',
                'views': [(tree_view.id, 'tree'), (form_view.id, 'form')],
                'context': {
                    'default_employee_id': this.employee_id.id,
                    'default_department_id': this.transfer_department.id,
                    'default_branch_id': this.transfer_branch.id,
                    'default_company_id': this.transfer_company.id,
                },
                'domain': [('employee_id', '=', self.employee_id.id)],
            }

    def employee_new_payslip_create_request(self):
        self.sudo().ensure_one()
        context = dict(self._context or {})
        active_model = context.get('active_model')
        form_view = self.sudo().env.ref('om_hr_payroll.view_hr_payslip_form')
        tree_view = self.sudo().env.ref('om_hr_payroll.view_hr_payslip_tree')
        return {
            'name': _('Payslip'),
            'res_model': 'hr.payslip',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'views': [(tree_view.id, 'tree'), (form_view.id, 'form')],
            'domain': [('employee_id', '=', self.employee_id.id)],
        }

    def employee_gratuity_action(self):
        self.sudo().ensure_one()
        context = dict(self._context or {})
        active_model = context.get('active_model')
        form_view = self.sudo().env.ref('account.view_move_form')
        tree_view = self.sudo().env.ref('account.view_move_tree')
        return {
            'name': _('Gratuity'),
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'views': [(tree_view.id, 'tree'), (form_view.id, 'form')],
            'domain': [('company_transfer_id', '=', self.id)],
        }

    def compute_employee_notice_period_button(self):
        count = 0
        if self.transfer_type == 'temp':
            date_from = self.start_date
            date_to = self.end_date
            import datetime
            d11 = str(date_from)
            dt21 = datetime.datetime.strptime(d11, '%Y-%m-%d')
            date1 = dt21.strftime("%d/%m/%Y")
            d22 = str(date_to)
            dt22 = datetime.datetime.strptime(d22, '%Y-%m-%d')
            date2 = dt22.strftime("%d/%m/%Y")
            notice_days = (date_to - date_from).days
            count = notice_days
            self.employee_notice_period = count
        else:
            self.employee_notice_period = 0

    def employee_leave_allocation_info(self):
        self.sudo().ensure_one()
        context = dict(self._context or {})
        active_model = context.get('active_model')
        tree_view = self.sudo().env.ref('hr_holidays.hr_leave_report_tree')
        for this in self:
            if this._context is None:
                context = {}
            partner = {}
            for m in this:
                partner = {
                    'name': m.employee_id.name,
                    'company_id': m.transfer_department.id,
                }
            return {
                'name': _('Time Off Analysis'),
                'res_model': 'hr.leave.report',
                'type': 'ir.actions.act_window',
                'view_mode': 'tree',
                'views': [(tree_view.id, 'tree')],
                'context': {
                    'default_employee_id': this.employee_id.id,
                    'default_department_id': this.transfer_department.id,
                },
                'domain': [('employee_id', '=', self.employee_id.id)],
            }

    def _compute_employee_contract_count(self):
        self.employee_contract_count = self.env['hr.contract'].sudo().search_count(
            [('employee_id', '=', self.employee_id.id)])

    #
    def _compute_employee_payslip_count(self):
        self.employee_payslip_count = self.env['hr.payslip'].sudo().search_count(
            [('employee_id', '=', self.employee_id.id)])

    #
    def _compute_employee_leave_request(self):
        self.employee_leave_request = self.env['hr.leave'].sudo().search_count(
            [('employee_id', '=', self.employee_id.id)])

    def _compute_employee_gratity_count(self):
        self.employee_gratuity_count = self.env['account.move'].sudo().search_count(
            [('company_transfer_id', '=', self.id)])

    @api.model
    def create(self, values):
        if values['record_type'] == 'inter':
            values['name'] = self.sudo().env['ir.sequence'].get('company.transfer') or 'New Inter Transfer'
        else:
            values['name'] = self.sudo().env['ir.sequence'].get('intra.company.transfer') or 'New Intra Transfer'
        res = super(CompanyToCompanyTransfer, self).create(values)
        return res

    @api.depends('employee_id')
    def _compute_employee_count(self):
        for user in self.with_context(active_test=False):
            user.employee_count = len(user.employee_id)

    @api.onchange('end_date')
    def get_end_date(self):
        date = self.start_date
        if self.end_date:
            if self.end_date < date:
                raise ValidationError("End Date should be greater than start date")

    # def cancel_state(self):
    #
    #     ddd = self.env['hr.contract'].search([('employee_id', '=', self.employee_id.id), ('state', '=', 'open')])
    #     for i in ddd:
    #         i.write({
    #             'state': 'cancel'
    #         })
    #     self.create_hr_contract()
    #
    # def create_hr_contract(self):
    #     contract = self.env['hr.contract'].create({
    #         'state': 'open',
    #         'name': "test1",
    #         'wage': self.transfer_employee_wage,
    #         'employee_id': self.employee_id.id,
    #         'hr_responsible_id': 1,
    #         'struct_id': 1,
    #         'date_start': self.start_date,
    #         'date_end': self.end_date,
    #
    #     })

    def employee_probation_notify(self):
        if self.state == 'transfer' and self.employee_notice_period == 1:
            self.sudo().write({'state': 'probation'})
        else:
            self.employee_notice_period = 0
        ctx = self.sudo().env.context.copy()
        current_user = self.env.user.name
        current_url = self.sudo().env['ir.config_parameter'].sudo().get_param('web.base.url')
        current_url += '/web#id=%d&view_type=form&model=%s' % (self.id, self._name)
        ctx.update({
            'name': self.name,
            'employee': self.employee_id.name,
            'url': current_url,
            'current_user': current_user,
            'current_company': self.current_company.name,
            'transfer_company': self.transfer_company.name,
            'current_reporting_manager': self.current_reporting_manager.name,
            'transferred_reporting_manager': self.transfer_reporting_manager.name,
            'employee_notice_period': self.employee_notice_period,
            'date': self.requested_date,
            'email_to': self.employee_id.work_email,
            'email_cc': self.transfer_reporting_manager.work_email,
        })
        # template = self.sudo().env.ref(
        #     'hr_employee_orientation.email_template_request_for_company_company_transfer_reverse',
        #     False)
        # template.with_context(ctx).sudo().send_mail(self.id, force_send=True)

    def get_previous_transfer_reporting_manager(self):
        cc = ''

        cc = str(self.sudo().current_reporting_manager.work_email) + ',' + cc
        cc = str(self.sudo().transfer_reporting_manager.work_email) + ',' + cc
        cc = cc.rstrip(',')
        return cc

    def cancel_transfer(self):
        obj_emp = self.sudo().env['hr.employee'].browse(self.employee_id.id)
        emp = {
            'name': self.sudo().employee_id.name,
            'company_id': self.sudo().current_company.id,
        }
        obj_emp.write(emp)
        for obj_contract in self.sudo().env['hr.contract'].sudo().search([('employee_id', '=', self.employee_id.id)]):
            # obj_contract.unlink()
            obj_contract.sudo().write({'state': 'cancel'})
            self.state = 'transfer'

    def create_leave_current_company_allocation(self):
        leave_allocation = self.env['hr.leave.allocation'].sudo().search(
            [('employee_id', '=', self.employee_id.id), ('holiday_status_id.code', '!=', 'AL'),
             ('company_id', '=', self.transfer_company.id), ('state', '=', 'validate')])
        print("AGSYUGSUYAS", leave_allocation)
        for leave in leave_allocation:
            transfer_company_code = self.env['hr.leave.type'].sudo().search(
                [('company_id', '=', self.current_company.id), ('code', '=', leave.holiday_status_id.code),
                 ('code', '!=', 'AL')])
            print("TRANSFERRRRRRRRRRRRRRR", leave.id, leave.number_of_days, leave.leaves_taken)
            # err
            for transfer in transfer_company_code:
                if transfer.code == leave.holiday_status_id.code:
                    vals = {'name': 'Allocation of %s' % (transfer.name),
                            'employee_id': self.employee_id.id,
                            'holiday_status_id': transfer.id,
                            'holiday_type': leave.holiday_type,
                            'number_of_days': leave.number_of_days - leave.leaves_taken,
                            'number_of_days_display': leave.number_of_days - leave.leaves_taken,
                            'department_id': self.current_department.id,
                            'company_id': self.current_company.id,
                            }
                    leave_create = self.env['hr.leave.allocation'].sudo().create(vals)
                    leave_create.sudo().action_approve()
                    leave_create.sudo().action_validate()
                    print("WORKKKKKKKKKKKKKKKKKKKKKKKKKKK", vals)
                    # leave_create.sudo().compute_leave_entitlement()
                    # leave_create.sudo()._onchange_holiday_status_id()
            print("TEST")

    # def create_leave_allocation(self):
    #     leave_allocation = self.env['hr.leave.allocation'].sudo().search(
    #         [('employee_id', '=', self.employee_id.id), ('holiday_status_id.code', '!=', 'AL'),
    #          ('state', '=', 'validate'), ('company_id', '=', 'company_id')])
    #
    #     for company in leave_allocation:
    #         if company

    # # print("::::::::::::::::::::::::::::::::::::::::::::::::::")
    # leave_allocation = self.env['hr.leave.allocation'].sudo().search(
    #     [('employee_id', '=', self.employee_id.id), ('holiday_status_id.code', '!=', 'AL'),
    #      ('state', '=', 'validate'), ('company_id', '=', 'company_id')])
    #
    # for company in leave_allocation:
    #

    # for leave in leave_allocation:
    #     transfer_company_code = self.env['hr.leave.type'].sudo().search(
    #         [('code', '=', leave.holiday_status_id.code),
    #          ('code', '!=', 'AL')])
    #     print("::::::::::::::1111111111111111111111111111111111::::::::::::::::::::::::::::::::::::", transfer_company_code)
    #     for transfer in transfer_company_code:
    #         print("::::::::::::::2222222222222222222222222222::::::::::::::::::::::::::::::::::::")
    #         if transfer.code == leave.holiday_status_id.code:
    #             print("::::::::::::::3333333333333333333333::::::::::::::::::::::::::::::::::::")
    #             vals = {'name': 'Allocation of %s' % (transfer.name),
    #                     'employee_id': self.employee_id.id,
    #                     'holiday_status_id': transfer.id,
    #                     'holiday_type': leave.holiday_type,
    #                     'number_of_days': leave.number_of_days - leave.leaves_taken,
    #                     'number_of_days_display': leave.number_of_days - leave.leaves_taken,
    #                     'department_id': self.transfer_department.id,
    #                     # 'company_id': self.transfer_company.id,
    #                     }
    #             leave_create = self.env['hr.leave.allocation'].sudo().create(vals)
    #             leave_create.sudo().action_confirm()
    #             print("OOOOOOOOOOOOOOnnnnnnnnnnnnOOOOOOOOOOOOOOOOOO",leave_create)
    #             # leave_create.sudo().compute_leave_entitlement()
    #             # leave_create.sudo()._onchange_holiday_status_id()
    #             return leave_create.id

    def cancel_transfered_company_create_leave_allocation(self):
        leave_allocation = self.env['hr.leave.allocation'].sudo().search(
            [('employee_id', '=', self.employee_id.id), ('holiday_status_id.code', '!=', 'AL'),
             ('company_id', '=', self.transfer_company.id)])
        print("ALLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL", leave_allocation)
        # err
        # print("LEAVEEEEEEEEEE",leave_allocation)
        for leave in leave_allocation:
            if leave.state != 'refuse':
                print("SIAISHIASUS", leave.id, leave.state)
                leave.sudo().action_refuse()

    def cancel_create_leave_allocation(self):
        leave_allocation = self.env['hr.leave.allocation'].sudo().search(
            [('employee_id', '=', self.employee_id.id), ('holiday_status_id.code', '!=', 'AL'),
             ])

        for leave in leave_allocation:
            if leave.state != 'refuse':
                print("SIAISHIASUS", leave.id, leave.state)
                leave.action_refuse()

    def create_new_transfer_payslip(self):
        ttyme = datetime.fromtimestamp(time.mktime(time.strptime(str(self.requested_date), "%Y-%m-%d")))
        locale = self.sudo().env.context.get('lang') or 'en_US'
        # print("ffsdfdsfsd",self.start_date.strftime('%d'))
        # err
        if self.start_date.strftime('%d') == '01':
            first_date = self.start_date - timedelta(days=1)
            payslip = self.env['hr.payslip'].sudo().create({
                'employee_id': self.employee_id.id,
                'name': _('Salary Slip of %s for %s') % (
                    self.employee_id.name,
                    tools.ustr(babel.dates.format_date(date=ttyme, format='MMMM-y', locale=locale))),
                'number': 'Contract for ' + str(self.employee_id.name),
                'date_to': self.start_date - timedelta(days=1),
                'date': self.requested_date,
                'company_id': self.current_company.id,
                'branch_id': self.current_branch.id,
                'contract_id': self.employee_current_contract.id,
                # 'journal_id': self.employee_current_salary_journal.id,
                'struct_id': self.employee_current_salary_structure.id,
                'date_from': first_date.replace(day=1),
                'intercompany_transfer': True,
            })
            payslip.onchange_employee()
            payslip.compute_sheet()
            self.payslip_generated = True
            # print("DDDDDDDDDDDDDDDDDDDDDDDVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV",self.start_date.strftime('%d'))

        else:

            payslip = self.env['hr.payslip'].sudo().create({
                'employee_id': self.employee_id.id,
                'name': _('Salary Slip of %s for %s') % (
                    self.employee_id.name,
                    tools.ustr(babel.dates.format_date(date=ttyme, format='MMMM-y', locale=locale))),
                'number': 'Contract for ' + str(self.employee_id.name),
                'date_to': self.start_date - timedelta(days=1),
                'date': self.requested_date,
                'company_id': self.current_company.id,
                'branch_id': self.current_branch.id,
                'contract_id': self.employee_current_contract.id,
                # 'journal_id': self.employee_current_salary_journal.id,
                'struct_id': self.employee_current_salary_structure.id,
                'date_from': self.start_date.replace(day=1),
                'intercompany_transfer': True,
            })
            payslip.onchange_employee()
            payslip.compute_sheet()
            self.payslip_generated = True

    def reverse_new_transfer_contract(self):
        contract = self.sudo().env['hr.contract'].sudo().create({
            'name': 'Contract for ' + str(self.employee_id.name),
            'notes': 'Contract (Transfer) for ' + str(self.employee_id.name),
            'employee_id': self.employee_id.id,
            'date_start': self.requested_date,
            'date_end': self.end_date,
            'company_id': self.current_company.id,
            'job_id': self.current_job.id,
            'department_id': self.current_department.id,
            # 'basic': self.current_employee_basic,
            # 'housing_allowance': self.current_employee_housing_allowance,
            'travel_allowance': self.current_employee_travel_allowance,
            'other_allowance': self.current_employee_other_allowance,
            'wage': self.current_employee_wage,
            'struct_id': self.employee_id.current_contract.struct_id.id,
            'journal_id': self.journal_id.id,
            'state': 'open',
        })
        return contract

    def create_new_transfer_contract(self):
        contract = self.sudo().env['hr.contract'].sudo().create({
            'name': 'Contract for ' + str(self.employee_id.name),
            'notes': 'Contract (Transfer) for ' + str(self.employee_id.name),
            'employee_id': self.employee_id.id,
            'date_start': self.requested_date,
            'date_end': self.end_date,
            'company_id': self.transfer_company.id,
            'job_id': self.transfer_job.id,
            'department_id': self.transfer_department.id,
            # 'basic': self.transfer_employee_basic,
            # 'housing_allowance': self.transfer_employee_housing_allowance,
            'travel_allowance': self.transfer_employee_travel_allowance,
            'other_allowance': self.transfer_employee_other_allowance,
            'wage': self.transfer_employee_wage,
            'struct_id': self.struct_id.id,
            # 'journal_id': self.journal_id.id,
            'state': 'open',
        })
        print("22222222222222222222", contract)
        return contract

    def action_approve(self):
        amount = 0.0
        for line in self:
            if not line.approval_person.user_id.id == self.env.uid:
                raise ValidationError(_("You are not allowed to approve..!Approval person only approve."))
            else:
                # loan = self.env['hr.loan.line'].search([('employee_id','=',line.employee_id.id),
                #                                         ('date', '<=', line.end_date),('date','>=', line.start_date),
                #                                         ('done_deduction','=',False)])
                # print(loan,"loan")
                # loan_amount = 0.0
                # if loan:
                #     loan_amount = 0.0
                #     for lo in loan:
                #         print(lo.loan_id.name, "name")
                #         print(lo.done_deduction,"done_deduction")
                #         loan_amount += lo.amount
                #
                # if loan_amount > 0.0:
                #     raise ValidationError(_("Loan Installment was pending.Please Process Loan Deduction and Confirm..!"))
                line.account_post()
                line.sudo().approved_mail()
                line.write({'state': 'approve'})

    def create_new_transfer_company_payslip(self):
        import calendar
        test_date = self.start_date
        end_dates = calendar.monthrange(test_date.year, test_date.month)[1]
        ttyme = datetime.fromtimestamp(time.mktime(time.strptime(str(self.requested_date), "%Y-%m-%d")))
        locale = self.sudo().env.context.get('lang') or 'en_US'
        if self.start_date.strftime('%d') == 1:
            print("DDDDDDDDDDDDDDDDDDDDDDDVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV", self.start_date.strftime('%d'))

        else:
            contract = self.env['hr.contract'].sudo().search(
                [('employee_id', '=', self.employee_id.id), ('company_id', '=', self.transfer_company.id),
                 ('state', '=', 'open')], limit=1)

            payslip = self.env['hr.payslip'].create({
                'employee_id': self.employee_id.id,
                'name': _('Salary Slip of %s for %s') % (
                    self.employee_id.name,
                    tools.ustr(babel.dates.format_date(date=ttyme, format='MMMM-y', locale=locale))),
                'number': 'Contract for ' + str(self.employee_id.name),
                'date_to': self.start_date - timedelta(days=1),
                'date': self.requested_date,
                'company_id': self.transfer_company.id,
                'branch_id': self.transfer_branch.id,
                'contract_id': contract.id,
                # 'journal_id': self.employee_current_salary_journal.id,
                'struct_id': self.struct_id.id,
                'date_from': self.start_date,
                'date_to': self.start_date.replace(day=end_dates),
                # 'intercompany_transfer': True,
                'state': 'done'
            })
            payslip.onchange_employee()
            payslip.compute_sheet()


class ResCompany(models.Model):
    _inherit = 'res.company'
    _description = 'Res Company'
    journal_id = fields.Many2one('account.journal', string="Journal", required=True)
    gratuity_debit_account_id = fields.Many2one('account.account', string="Debit account", required=True)
    gratuity_credit_account_id = fields.Many2one('account.account', string="credit account", required=True)


class AccountMove(models.Model):
    _inherit = 'account.move'
    _description = 'Account move'

    company_transfer_id = fields.Many2one('company.transfer', string="Company Transfer", required=True)

# class HRLeaveReport(models.Model):
#     _inherit = 'hr.leave.report'
#     _description = 'HR Leave Report'
#
#     company_name = fields.Many2one("hr.employee", string=" Company")

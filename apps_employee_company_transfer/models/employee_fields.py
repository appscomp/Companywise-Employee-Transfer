from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from odoo import api, fields, models, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    first_name = fields.Char(string="First Name")
    last_name = fields.Char(string="Last Name")
    name_in_wps = fields.Char(string=" Name In WPS")
    saturday_off = fields.Selection([
        ('alternativeoff', 'Alternative OFF'),
        ('working', 'Working'),
    ])
    date_of_joining = fields.Datetime(string="Date of Joining")
    employee_status = fields.Selection([
        ('', ''),
        ('trainee', 'Trainee'),
        ('probation', 'Probation'),
        ('probation', 'Probation'),
        ('permanant', 'Permanant'),
        ('noticeperiod', 'Notice Period'),
        ('vacation', 'Vacation'),
        ('shortbreak', 'Short Break'),
    ])
    probation_month = fields.Char(string="Probation Month ")
    date_of_permanancy = fields.Datetime(string="Date of Permanency")
    insurance_no = fields.Char(string="Insurance Number")
    branch = fields.Many2one("res.branch", string="Branch", required=True)
    grade = fields.Many2one("employee.grade", string="Grade", required=True)
    designation = fields.Char(string="Designation")
    reporting_manager = fields.Many2one("hr.employee", string="Reporting Manager", required=True)
    supervisor = fields.Many2one("hr.employee", required=True, string="Reporting Head")
    current_contract = fields.Many2one("hr.contract", required=True, string="Currnet Contract")
    basic = fields.Float(string="Basic")
    housing_allowance = fields.Float(string="Housing Allowance")
    travel_allowance = fields.Float(string="Travel Allowance")
    other_allowance = fields.Float(string="Other Allowance")
    wage = fields.Float(string="Wage")
    joining_date = fields.Datetime(string="Date of Joining")
    work_loc_id = fields.Many2one('res.branch', string="Work Location", required=True)


class EmployeeGrade(models.Model):
    _name = 'employee.grade'
    _description = 'Employee Grade'
    _rec_name = 'grade'
    grade = fields.Char(string="Grade")


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'
    _description = 'hr.payslip'

    branch_id = fields.Many2one('hr.employee', string="Branch")

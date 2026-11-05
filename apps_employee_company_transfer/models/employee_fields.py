from odoo import api, fields, models, _


class EmployeeGrade(models.Model):
    _name = 'employee.grade'
    _description = 'Employee Grade'
    _rec_name = 'grade'
    _order = 'level, grade'

    grade = fields.Char(string="Grade", required=True)
    level = fields.Integer(
        string="Level", default=1,
        help="Numeric level of the grade. A transfer of an employee whose grade level is above 2 "
             "requires a supervisor in the target company.")

    _grade_uniq = models.Constraint('unique(grade)', 'This grade already exists.')


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # prefetch=False: these business fields are not part of hr.employee.public. Without it the ORM
    # prefetches them with any field of the employee and raises an AccessError for users without
    # HR access (e.g. the POS cashiers, who read employees of pos_hr).

    first_name = fields.Char(string="First Name", prefetch=False)
    last_name = fields.Char(string="Last Name", prefetch=False)
    name_in_wps = fields.Char(string="Name In WPS", prefetch=False)
    saturday_off = fields.Selection([
        ('alternativeoff', 'Alternative OFF'),
        ('working', 'Working'),
    ], string="Saturday Schedule", prefetch=False)
    employee_status = fields.Selection([
        ('trainee', 'Trainee'),
        ('probation', 'Probation'),
        ('permanant', 'Permanent'),
        ('noticeperiod', 'Notice Period'),
        ('vacation', 'Vacation'),
        ('shortbreak', 'Short Break'),
    ], string="Employee Status", prefetch=False)
    probation_month = fields.Char(string="Probation Month", prefetch=False)
    date_of_permanancy = fields.Date(string="Date of Permanency", prefetch=False)
    insurance_no = fields.Char(string="Insurance Number", prefetch=False)
    branch = fields.Many2one("res.branch", string="Branch", tracking=True, prefetch=False)
    grade = fields.Many2one("employee.grade", string="Grade", tracking=True, prefetch=False)
    designation = fields.Char(string="Designation", prefetch=False)
    reporting_manager = fields.Many2one("hr.employee", string="Reporting Manager", tracking=True, prefetch=False)
    supervisor = fields.Many2one("hr.employee", string="Reporting Head", tracking=True, prefetch=False)
    basic = fields.Float(string="Basic", groups="hr.group_hr_user")
    housing_allowance = fields.Float(string="Housing Allowance", groups="hr.group_hr_user")
    travel_allowance = fields.Float(string="Travel Allowance", groups="hr.group_hr_user")
    other_allowance = fields.Float(string="Other Allowance", groups="hr.group_hr_user")
    joining_date = fields.Date(string="Date of Joining", prefetch=False)
    date_of_joining = fields.Date(
        string="Date of Joining (alias)", related='joining_date', readonly=False,
        help="Kept for compatibility, same value as the Date of Joining.", prefetch=False)
    work_loc_id = fields.Many2one(
        'res.branch', string="Work Branch", domain="[('company_id', '=', company_id)]", prefetch=False)

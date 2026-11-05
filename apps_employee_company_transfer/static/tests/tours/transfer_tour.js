/** @odoo-module **/
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("apps_employee_company_transfer_tour", {
    url: "/odoo",
    steps: () => [
        {
            trigger: ".o_menu_toggle, .o_navbar_apps_menu button",
            run: "click",
        },
        {
            trigger: ".o_app[data-menu-xmlid='hr.menu_hr_root']",
            run: "click",
        },
        {
            trigger: "button.dropdown-toggle:contains('Transfers')",
            run: "click",
        },
        {
            trigger: ".dropdown-item:contains('Inter-Company Employee Transfer')",
            run: "click",
        },
        {
            trigger: ".o_list_view, .o_view_nocontent",
        },
        {
            trigger: ".o_list_button_add",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='employee_id'] input",
            run: "edit Tour Employee",
        },
        {
            trigger: ".ui-autocomplete .ui-menu-item a:contains('Tour Employee')",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='current_company'] :contains('Tour Co A'), .o_field_widget[name='current_company']:contains('Tour Co A')",
        },
        {
            trigger: ".o_field_widget[name='transfer_company'] input",
            run: "edit Tour Co B",
        },
        {
            trigger: ".ui-autocomplete .ui-menu-item a:contains('Tour Co B')",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='transfer_branch'] input",
            run: "edit TB1",
        },
        {
            trigger: ".ui-autocomplete .ui-menu-item a:contains('TB1')",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='transfer_department'] input",
            run: "edit Tour Dept B",
        },
        {
            trigger: ".ui-autocomplete .ui-menu-item a:contains('Tour Dept B')",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='transfer_job'] input",
            run: "edit Tour Job B",
        },
        {
            trigger: ".ui-autocomplete .ui-menu-item a:contains('Tour Job B')",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='transfer_grade_id'] input",
            run: "edit 2",
        },
        {
            trigger: ".ui-autocomplete .ui-menu-item a:contains('2')",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='transfer_reporting_manager'] input",
            run: "edit Tour Manager B",
        },
        {
            trigger: ".ui-autocomplete .ui-menu-item a:contains('Tour Manager B')",
            run: "click",
        },
        {
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            trigger: ".o_statusbar_status .o_arrow_button_current:contains('Draft')",
        },
        {
            trigger: "button[name='submit_employee_company_transfer']",
            run: "click",
        },
        {
            trigger: ".o_statusbar_status .o_arrow_button_current:contains('Waiting')",
        },
        {
            trigger: "button[name='approve_employee_company_transfer']",
            run: "click",
        },
        {
            trigger: ".o_statusbar_status .o_arrow_button_current:contains('Approved')",
        },
        {
            trigger: "button[name='update_employee_company_transfer']",
            run: "click",
        },
        {
            trigger: ".modal-footer .btn-primary",
            run: "click",
        },
        {
            trigger: ".o_statusbar_status .o_arrow_button_current:contains('Transferred')",
        },
        {
            trigger: ".o_field_widget[name='name']",
        },
    ],
});

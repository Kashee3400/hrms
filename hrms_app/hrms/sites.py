from django.urls import path
from hrms_app.views import views, auth_views, report_view, announcement
from hrms_app.views import ShortLeaveCreateView,ShortLeaveUpdateView
from ..views.attendance_view import BulkAttendanceView, AttendancePreviewAjaxView, GetEmployeesAjaxView, \
    AttendanceStatsAjaxView
from ..views.leave_bulk import BulkLeaveCreateView,BulkLeaveHistoryView
from ..views.leave_bulk import LeaveBalanceInitializerView

class CustomSite:
    def __init__(self):
        self._registry = {}

    def register_view(self, url, view, name=None):
        wrapped_view = self.wrap_view(view)
        self._registry[url] = (wrapped_view, name)

    def has_permission(self, user, view):
        # sourcery skip: assign-if-exp, boolean-if-exp-identity, reintroduce-else
        if hasattr(view, 'permission_required'):
            permission = view.permission_required
            if user.has_perm(permission) or user.groups.filter(
                    permissions__codename=permission.split('.')[-1]).exists():
                return True
            return False
        return True

    def wrap_view(self, view):
        def view_wrapper(request, *args, **kwargs):
            # if not self.has_permission(request.user, view):
            #     return render(request, '403.html', status=403)
            return view.as_view()(request, *args, **kwargs)

        return view_wrapper

    def get_urls(self):
        urlpatterns = []
        for url, (view, name) in self._registry.items():
            if name:
                urlpatterns.append(path(url, view, name=name))
            else:
                urlpatterns.append(path(url, view))
        return urlpatterns


site = CustomSite()

app_name = 'hrms'
site.register_view('dashboard', views.HomePageView, name='dashboard')
site.register_view('login/', auth_views.LoginView, name='login')
site.register_view('logout/', auth_views.LogoutView, name='logout')
site.register_view('reset-password/', auth_views.PasswordResetView, name='reset_password')
site.register_view('reset-password-done/', auth_views.PasswordResetDoneView, name='password_reset_done')
site.register_view('reset-password-complete/', auth_views.PasswordResetCompleteView, name='password_reset_complete')
site.register_view('reset-password-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView,
                   name='password_reset_confirm')
site.register_view('password-change/', views.ChangePasswordView, name='password_change')
site.register_view('password-change-done/', auth_views.PasswordChangeDoneView, name='password_change_done')
site.register_view('leave-tracker/', views.LeaveTrackerView, name='leave_tracker')
site.register_view('calendar/', views.EventPageView, name='calendar')
site.register_view('', views.DashboardView, name='home')
site.register_view('attendance/<slug:slug>/', views.EventDetailPageView, name='event_detail')
site.register_view('attendance-log/<slug:slug>/', views.AttendanceLogActionView, name='attendance_log_action')
site.register_view('attendance-regularization/', views.AttendanceLogListView, name='regularization')
site.register_view('leave/apply/<int:leave_type>/', views.ApplyOrUpdateLeaveView, name='apply_leave_with_id')
site.register_view('leave/edit/<slug:slug>/', views.ApplyOrUpdateLeaveView, name='update_leave')
site.register_view('leave/<slug:slug>/', views.LeaveApplicationDetailView, name='leave_application_detail')
site.register_view('leave/<slug:slug>/update', views.LeaveApplicationUpdateView, name='leave_application_update')

site.register_view("short-leave/apply/", ShortLeaveCreateView, name='short_leave_create')
site.register_view('short-leave/<int:pk>/edit/', ShortLeaveUpdateView, name='short_leave_update')

site.register_view('leave/initializer', LeaveBalanceInitializerView, name='leave_intializer')



site.register_view('delete/<str:model_name>/<int:pk>/', views.GenericDeleteView, name='generic_delete')
site.register_view('leave-transaction/', views.LeaveTransactionCreateView, name='leave_transaction_create'),
site.register_view('leave-balance-update/', views.LeaveBalanceUpdateView, name='leave_bal_up'),
site.register_view('tour-tracker/', views.TourTrackerView, name='tour_tracker')
site.register_view('apply-tour/', views.ApplyTourView, name='apply_tour')
site.register_view('tour/<slug:slug>/', views.TourApplicationDetailView, name='tour_application_detail')
site.register_view('tour/<slug:slug>/update', views.TourApplicationUpdateView, name='tour_application_update')
site.register_view('tour/<slug:slug>/pdf', views.GenerateTourPDFView, name='generate_tour_pdf')
site.register_view('employees/', views.EmployeeListView, name='employees')
site.register_view('employee-profile/<int:pk>/', views.EmployeeProfileView, name='employee_profile')
site.register_view('personal-detail-update/<int:pk>/', views.PersonalDetailUpdateView, name='personal_detail_update')

###############################################################################################
######                                Reports URLS                                        #####
###############################################################################################
site.register_view('attendance-report/', report_view.MonthAttendanceReportView, name='attendance_report')
site.register_view('detailed-attendance-report/', report_view.DetailedMonthlyPresenceView,
                   name='detailed_attendance_report')
site.register_view('leave-balance-report/', report_view.LeaveBalanceReportView, name='leave_balance_report')
site.register_view('announcements/', announcement.AnnouncementView, name='announcements')
site.register_view('announcements/<int:pk>', announcement.AnnouncementView, name='announcement-update')
site.register_view('bulk-attendance/', BulkAttendanceView, name='bulk_attendance'),

site.register_view('bulk-leave-create/', BulkLeaveCreateView, name='bulk_leave_create'),
site.register_view('bulk-leave-history/', BulkLeaveHistoryView, name='bulk_leave_history'),

# Ajax endpoints for enhanced functionality
site.register_view('ajax/employees/', GetEmployeesAjaxView, name='get_employees_ajax'),
site.register_view('ajax/attendance-preview/', AttendancePreviewAjaxView, name='attendance_preview_ajax'),
site.register_view('ajax/attendance-stats/', AttendanceStatsAjaxView, name='attendance_stats_ajax'),
site.register_view('ajax/attendance-stats/', AttendanceStatsAjaxView, name='attendance_stats_ajax'),





from django.urls import path, include
from hrms_app.views.api_views import *
from hrms_app.views.leave_balance_view import ForwardLeaveBalanceView,CreditELLeaveView,UserAttendanceAggregation
from hrms_app.views.mobile_home_api import HomeSummaryAPIView, HomeTodayAPIView
from hrms_app.views.mobile_device_api import DeviceTokenView, DeviceTokenDetailView
from hrms_app.views.mobile_app_api import AppVersionAPIView
from hrms_app.views.mobile_attendance_api import (
    AttendanceCalendarView,
    HolidayListView,
    TeamMemberDayView,
    TeamMonthView,
    TeamTodayView,
)
from hrms_app.views.mobile_leave_api import (
    LeaveApplyOptionsView,
    LeaveApplyView,
    LeavePreviewView,
    MyLeaveCancelView,
    MyLeaveDetailView,
    MyLeaveListView,
    MyLeaveOverviewView,
    ShortLeaveApplyView,
    ShortLeavePreviewView,
    TeamLeaveActionView,
    TeamLeaveDetailView,
    TeamLeaveListView,
)
from hrms_app.views.mobile_gap_api import (
    ApprovalMailPreviewView,
    ApprovalMailSendView,
    AttendanceGapListView,
)
from hrms_app.views.mobile_notification_api import (
    NotificationFeedView,
    NotificationReadAllView,
    NotificationReadView,
)
from hrms_app.views.mobile_profile_api import (
    ChangePasswordView,
    ProfileAddressView,
    ProfileAvatarView,
    ProfileDetailsView,
    ProfileView,
)
from hrms_app.views.mobile_settings_api import AppSettingDetailView, AppSettingListView, ElPolicyView
from hrms_app.views.mobile_tour_api import (
    MyTourCancelView,
    MyTourDetailView,
    MyTourListView,
    MyTourRerequestView,
    TeamTourActionView,
    TeamTourDetailView,
    TeamTourListView,
    TourApplyOptionsView,
    TourOverviewView,
    TourPdfView,
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,TokenVerifyView
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'attendance-settings', AttendanceSettingViewSet)
router.register(r'attendance-status-colors', AttendanceStatusColorViewSet)
router.register(r'holidays', HolidayViewSet)
router.register(r'attendance-logs', AttendanceLogViewSet,basename='attendance-logs')
router.register(r'leave-openings', UserLeaveOpeningsViewSet, basename='user-leave-openings')
router.register(r'leavetype', LeaveTypeViewSet, basename='leavetype')
router.register(r'user', UserViewSet, basename='user')
router.register(r'device', DeviceInformationViewSet, basename='device')
router.register(r'tours', UserTourViewSet, basename='user-tour')
router.register(r'leave-applications', LeaveApplicationViewSet, basename='leaveapplication')

urlpatterns = [
    path('', include(router.urls)),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('personal-details/', PersonalDetailsView.as_view(), name='personal-details'),
    path('employee-shifts/', EmployeeShiftView.as_view(), name='employee-shifts'),
    path('attendance-choices/', AttendanceChoicesView.as_view(), name='attendance-choices'),
    path('notifications/', UserMonthlyNotificationsListView.as_view(), name='user_notifications'),
    path('notifications/<int:id>/', UpdateNotificationStatusView.as_view(), name='update-notification-status'),
    path("execute-populate-attendance/", ExecutePopulateAttendanceView.as_view(), name="execute_populate_attendance"),
    path('attendance-aggregation/', Top5EmployeesDurationAPIView.as_view(), name='attendance-aggregation'),
    path('get_top_5_employees/<int:year>/', Top5EmployeesView.as_view(), name='get_top_5_employees'),
    path("send_otp/", SendOTPView.as_view(), name="send_otp"),
    path("verify_otp/", VerifyOTPView.as_view(), name="verify_otp"),
    path('forward-leave-balances/', ForwardLeaveBalanceView.as_view(), name='forward-leave-balances'),
    path("credit-el-leaves/", CreditELLeaveView.as_view(), name="credit_el_leaves"),
    path("attendance-aggregation-count/", UserAttendanceAggregation.as_view(), name="attendance-aggregation-count"),
    path('leave-balances/initialize/', InitializeLeaveBalancesView.as_view(), 
         name='initialize-leave-balances'),
    path(
        "attendance/summary/",
        AttendanceSummaryAPIView.as_view(),
        name="attendance-summary",
    ),
    # Mobile app
    path("home/summary/", HomeSummaryAPIView.as_view(), name="mobile-home-summary"),
    path("home/today/", HomeTodayAPIView.as_view(), name="mobile-home-today"),
    path("attendance/calendar/", AttendanceCalendarView.as_view(), name="mobile-attendance-calendar"),
    path("devices/", DeviceTokenView.as_view(), name="mobile-devices"),
    path("devices/<str:token>/", DeviceTokenDetailView.as_view(), name="mobile-device-detail"),
    path("app/version/", AppVersionAPIView.as_view(), name="mobile-app-version"),
    path("leave/apply-options/", LeaveApplyOptionsView.as_view(), name="mobile-leave-apply-options"),
    path("leave/preview/", LeavePreviewView.as_view(), name="mobile-leave-preview"),
    path("leave/apply/", LeaveApplyView.as_view(), name="mobile-leave-apply"),
    path("leave/short/preview/", ShortLeavePreviewView.as_view(), name="mobile-short-leave-preview"),
    path("leave/short/apply/", ShortLeaveApplyView.as_view(), name="mobile-short-leave-apply"),
    path("leave/overview/", MyLeaveOverviewView.as_view(), name="mobile-leave-overview"),
    path("leave/my/", MyLeaveListView.as_view(), name="mobile-leave-my-list"),
    path("leave/my/<int:leave_id>/", MyLeaveDetailView.as_view(), name="mobile-leave-my-detail"),
    path("leave/my/<int:leave_id>/cancel/", MyLeaveCancelView.as_view(), name="mobile-leave-my-cancel"),
    path("leave/team/", TeamLeaveListView.as_view(), name="mobile-leave-team-list"),
    path("leave/team/<int:leave_id>/", TeamLeaveDetailView.as_view(), name="mobile-leave-team-detail"),
    path("leave/team/<int:leave_id>/action/", TeamLeaveActionView.as_view(), name="mobile-leave-team-action"),
    path("holiday/list/", HolidayListView.as_view(), name="mobile-holiday-list"),
    path("notifications/feed/", NotificationFeedView.as_view(), name="mobile-notification-feed"),
    path("notifications/feed/read-all/", NotificationReadAllView.as_view(), name="mobile-notification-read-all"),
    path("notifications/feed/<int:notification_id>/read/", NotificationReadView.as_view(), name="mobile-notification-read"),
    path("app-settings/", AppSettingListView.as_view(), name="mobile-app-settings"),
    path("app-settings/el-policy/", ElPolicyView.as_view(), name="mobile-app-settings-el-policy"),
    path("app-settings/<str:key>/", AppSettingDetailView.as_view(), name="mobile-app-setting-detail"),
    path("attendance/gaps/", AttendanceGapListView.as_view(), name="mobile-attendance-gaps"),
    path("attendance/team/", TeamMonthView.as_view(), name="mobile-team-month"),
    path("attendance/team/today/", TeamTodayView.as_view(), name="mobile-team-today"),
    path("attendance/team/<int:member_id>/day/", TeamMemberDayView.as_view(), name="mobile-team-member-day"),
    path("approval-mail/preview/", ApprovalMailPreviewView.as_view(), name="mobile-approval-mail-preview"),
    path("approval-mail/send/", ApprovalMailSendView.as_view(), name="mobile-approval-mail-send"),
    path("profile/", ProfileView.as_view(), name="mobile-profile"),
    path("profile/details/", ProfileDetailsView.as_view(), name="mobile-profile-details"),
    path("profile/address/<str:kind>/", ProfileAddressView.as_view(), name="mobile-profile-address"),
    path("profile/avatar/", ProfileAvatarView.as_view(), name="mobile-profile-avatar"),
    path("profile/change-password/", ChangePasswordView.as_view(), name="mobile-profile-change-password"),
    path("tour/apply-options/", TourApplyOptionsView.as_view(), name="mobile-tour-apply-options"),
    path("tour/overview/", TourOverviewView.as_view(), name="mobile-tour-overview"),
    path("tour/my/", MyTourListView.as_view(), name="mobile-tour-my-list"),
    path("tour/my/<int:tour_id>/", MyTourDetailView.as_view(), name="mobile-tour-my-detail"),
    path("tour/my/<int:tour_id>/cancel/", MyTourCancelView.as_view(), name="mobile-tour-my-cancel"),
    path("tour/my/<int:tour_id>/rerequest/", MyTourRerequestView.as_view(), name="mobile-tour-my-rerequest"),
    path("tour/pdf/<str:token>/", TourPdfView.as_view(), name="mobile-tour-pdf"),
    path("tour/team/", TeamTourListView.as_view(), name="mobile-tour-team-list"),
    path("tour/team/<int:tour_id>/", TeamTourDetailView.as_view(), name="mobile-tour-team-detail"),
    path("tour/team/<int:tour_id>/action/", TeamTourActionView.as_view(), name="mobile-tour-team-action"),

]

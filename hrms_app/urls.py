from django.urls import path, include
from hrms_app.views.api_views import *
from hrms_app.views.leave_balance_view import ForwardLeaveBalanceView,CreditELLeaveView,UserAttendanceAggregation
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

]

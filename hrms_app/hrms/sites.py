from django.urls import path
from django.shortcuts import render
from hrms_app.views import views
from hrms_app.views import auth_views


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
            if user.has_perm(permission) or user.groups.filter(permissions__codename=permission.split('.')[-1]).exists():
                return True
            return False
        return True

    def wrap_view(self, view):
        def view_wrapper(request, *args, **kwargs):
            if not self.has_permission(request.user, view):
                return render(request, '403.html', status=403)
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


site.register_view('', views.HomePageView, name='dashboard')
site.register_view('login/', auth_views.LoginView, name='login')
site.register_view('logout/', auth_views.LogoutView, name='logout')
site.register_view('reset-password/', auth_views.PasswordResetView, name='reset_password')
site.register_view('reset-password-done/', auth_views.PasswordResetDoneView, name='password_reset_done')
site.register_view('reset-password-complete/', auth_views.PasswordResetCompleteView, name='password_reset_complete')
site.register_view('reset-password-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView, name='password_reset_confirm')
site.register_view('password-change/', views.ChangePasswordView, name='password_change')
site.register_view('password-change-done/', auth_views.PasswordChangeDoneView, name='password_change_done')
site.register_view('leave-tracker/', views.LeaveTrackerView, name='leave_tracker')
site.register_view('apply-leave/', views.ApplyLeaveView, name='apply_leave')
site.register_view('attendance/', views.EventPageView, name='calendar')
site.register_view('attendance/<slug:slug>/', views.EventDetailPageView, name='event_detail')
site.register_view('profile/', views.ProfilePageView, name='profile')
site.register_view('apply-leave/<int:pk>/', views.ApplyLeaveView, name='apply_leave_with_id')
site.register_view('leave/<slug:slug>/', views.LeaveApplicationDetailView, name='leave_application_detail')
site.register_view('leave/<slug:slug>/update', views.LeaveApplicationUpdateView, name='leave_application_update')
site.register_view('holidays/', views.AddHolidaysView, name='holidays')
site.register_view('tour-tracker/', views.TourTrackerView, name='tour_tracker')
site.register_view('apply-tour/', views.ApplyTourView, name='apply_tour')
site.register_view('tour/<slug:slug>/', views.TourApplicationDetailView, name='tour_application_detail')
site.register_view('tour/<slug:slug>/update', views.TourApplicationUpdateView, name='tour_application_update')
site.register_view('tour/<int:pk>/delete', views.TourApplicationDeleteView, name='tour_application_delete')
site.register_view('tours/<slug:slug>/upload_bill/', views.UploadBillView, name='upload_bill')
site.register_view('employees/', views.EmployeeListView, name='employees')
site.register_view('employee-profile/<int:pk>/', views.EmployeeProfileView, name='employee_profile')

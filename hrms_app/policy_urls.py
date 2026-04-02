"""
urls.py — Leave Policy Config URLs

Include in your main urls.py:
    path("leave/policy-config/", include("leave.urls_policy_config", namespace="leave")),

Or add directly to your existing leave/urls.py under the appropriate prefix.
"""

from django.urls import path
from .views.policy_views import (
    LeavePolicyConfigListView,
    LeavePolicyConfigCreateView,
    LeavePolicyConfigUpdateView,
    LeavePolicyConfigHistoryView,
    LeavePolicyConfigCompareView,
)

app_name = "leave"

urlpatterns = [
    # List — /leave/policy-config/
    path(
        "",
        LeavePolicyConfigListView.as_view(),
        name="policy_config_list",
    ),

    # Create new version — /leave/policy-config/create/<leave_type_id>/
    path(
        "create/<int:leave_type_id>/",
        LeavePolicyConfigCreateView.as_view(),
        name="policy_config_create",
    ),

    # Edit active version — /leave/policy-config/edit/<pk>/
    path(
        "edit/<int:pk>/",
        LeavePolicyConfigUpdateView.as_view(),
        name="policy_config_edit",
    ),

    # AJAX: version history — /leave/policy-config/history/<leave_type_id>/
    path(
        "history/<int:leave_type_id>/",
        LeavePolicyConfigHistoryView.as_view(),
        name="policy_config_history",
    ),

    # AJAX: compare two versions — /leave/policy-config/compare/?a=<id>&b=<id>
    path(
        "compare/",
        LeavePolicyConfigCompareView.as_view(),
        name="policy_config_compare",
    ),
]
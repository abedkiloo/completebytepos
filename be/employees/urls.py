from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmployeeViewSet
from .leave_views import LeaveAllowanceView, LeaveDecisionView, LeaveRequestListView

router = DefaultRouter()
router.register(r'employees', EmployeeViewSet, basename='employee')

urlpatterns = [
    path('leave-requests/', LeaveRequestListView.as_view(), name='leave-requests'),
    path('leave-allowance/', LeaveAllowanceView.as_view(), name='leave-allowance'),
    path('leave-requests/<int:pk>/decide/', LeaveDecisionView.as_view(), name='leave-decide'),
    path('', include(router.urls)),
]

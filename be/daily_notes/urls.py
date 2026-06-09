from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DailyNoteViewSet, DailyTaskViewSet

router = DefaultRouter()
router.register(r'notes', DailyNoteViewSet, basename='daily-note')
router.register(r'tasks', DailyTaskViewSet, basename='daily-task')

urlpatterns = [
    path('', include(router.urls)),
]

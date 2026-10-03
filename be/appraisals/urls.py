from django.urls import path

from .views import (
    AppraisalIncrementDecideView,
    AppraisalIncrementListView,
    AppraisalMeView,
    AppraisalPolicyView,
    AppraisalTeamView,
)

urlpatterns = [
    path('policy/', AppraisalPolicyView.as_view(), name='appraisal-policy'),
    path('me/', AppraisalMeView.as_view(), name='appraisal-me'),
    path('team/', AppraisalTeamView.as_view(), name='appraisal-team'),
    path('increments/', AppraisalIncrementListView.as_view(), name='appraisal-increments'),
    path(
        'increments/<int:pk>/decision/',
        AppraisalIncrementDecideView.as_view(),
        name='appraisal-increment-decision',
    ),
]

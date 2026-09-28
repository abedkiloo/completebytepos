from django.urls import path

from .views import AppraisalMeView, AppraisalPolicyView, AppraisalTeamView

urlpatterns = [
    path('policy/', AppraisalPolicyView.as_view(), name='appraisal-policy'),
    path('me/', AppraisalMeView.as_view(), name='appraisal-me'),
    path('team/', AppraisalTeamView.as_view(), name='appraisal-team'),
]

from django.urls import path

from .nanobananapro import SmilePreviewStatusView, StartSmilePreviewView
from .views import AnalyzeSmileView

app_name = 'ai'

urlpatterns = [
    path('analyze-smile/', AnalyzeSmileView.as_view(), name='analyze-smile'),
    path('smile-preview/', StartSmilePreviewView.as_view(), name='smile-preview-start'),
    path('smile-preview/<str:task_id>/', SmilePreviewStatusView.as_view(), name='smile-preview-status'),
]

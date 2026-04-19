from django.urls import path

from .views import AnalyzeSmileView

app_name = 'ai'

urlpatterns = [
    path('analyze-smile/', AnalyzeSmileView.as_view(), name='analyze-smile'),
]

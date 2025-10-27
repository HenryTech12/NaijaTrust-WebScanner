from django.contrib import admin
from django.urls import path
from .views import APIScannerView

urlpatterns = [
    path('scan',APIScannerView.as_view(), name="scan_data")
]
 
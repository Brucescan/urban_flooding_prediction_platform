from django.urls import path

from .views import NDVIListAPI, NDVIDownloadAPI

urlpatterns = [
    path('ndvi/', NDVIListAPI.as_view(), name='ndvi-list'),
    path('ndvi/<int:pk>/download/', NDVIDownloadAPI.as_view(), name='ndvi-download'),
]
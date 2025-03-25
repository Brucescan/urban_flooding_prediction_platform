from django.urls import path
from .views import RasterMetadataAPI

urlpatterns = [
    path('rasters/', RasterMetadataAPI.as_view(), name='raster-metadata-api'),
]
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/users/", include("user_api.urls")),  # 修改路径为'user_api.urls'
]
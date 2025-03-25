from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    # admin管理路由
    path("api/users/", include("user_api.urls")),
    # 用户接口相关路由
    path('api/geodata/', include('geodata.urls')),
    # 获取数据的路由
]
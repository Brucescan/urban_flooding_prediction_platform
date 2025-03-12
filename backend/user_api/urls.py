from django.urls import path
from .views import register, LoginView, logout, GetCurrentUserView, search_users, delete_user

urlpatterns = [
    path('register/', register, name='register'),
    path('login/', LoginView.as_view(), name='login'),  # 修改为使用 LoginView 类
    path('logout/', logout, name='logout'),
    path('current/', GetCurrentUserView.as_view(), name='get_current_user'),  # 修改为使用 GetCurrentUserView 类
    path('search/', search_users, name='search_users'),
    path('delete/', delete_user, name='delete_user'),
]

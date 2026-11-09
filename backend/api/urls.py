from django.urls import re_path
from . import views

urlpatterns = [
    re_path(r"^auth/login/?$", views.auth_login),
    re_path(r"^auth/logout/?$", views.auth_logout),
    re_path(r"^auth/me/?$", views.auth_me),
    re_path(r"^categories/?$", views.categories),
    re_path(r"^categories/(?P<pk>[^/]+)/?$", views.category_detail),
    re_path(r"^products/?$", views.products),
    re_path(r"^products/(?P<pk>[^/]+)/?$", views.product_detail),
    re_path(r"^users/?$", views.users),
    re_path(r"^users/(?P<pk>[^/]+)/?$", views.user_detail),
]

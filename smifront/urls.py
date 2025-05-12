"""
URL configuration for smifront project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.urls import path

from smifront import views_auth, views_dashboard, views
from smifront.sitemaps import sitemaps, RobotsTxtView  # Import correct du dictionnaire sitemaps
from smifront.views import *
from django.conf.urls import handler404
from django.conf import settings

handler404 = 'smifront.view_error.handler404'

urlpatterns = [
    # index
    path('', index, name='index'),

    # Pages d'authentification
    path('login/', views_auth.login_view, name='login'),
    path('logout/', views_auth.logout_view, name='logout'),
    path('signup/', views_auth.signup_view, name='signup'),
    path('verify-account/', views_auth.verify_account_view, name='verify_account'),
    path('resend-verification/', views_auth.resend_verification_code, name='resend_verification'),

    # Dashboard principal
    path('dashboard/', views_dashboard.dashboard_view, name='dashboard'),

    path('admin/users/create/', views.admin_users_create, name='admin_users_create'),
    path('admin/users/update/', views.admin_users_update, name='admin_users_update'),
    path('admin/users/delete/', views.admin_users_delete, name='admin_users_delete'),

    # Routes pour les catégories
    path('admin/categories/', views.admin_categories, name='admin_categories'),
    path('admin/categories/create/', views.admin_categories_create, name='admin_categories_create'),
    path('admin/categories/update/', views.admin_categories_update, name='admin_categories_update'),
    path('admin/categories/delete/', views.admin_categories_delete, name='admin_categories_delete'),
    path('admin/categories/check-name/', views.admin_check_category_name, name='admin_check_category_name'),

    # Routes pour les produits
    path('admin/products/', views.admin_products, name='admin_products'),
    path('admin/products/create/', views.admin_products_create, name='admin_products_create'),
    path('admin/products/update/', views.admin_products_update, name='admin_products_update'),
    path('admin/products/delete/', views.admin_products_delete, name='admin_products_delete'),
    path('admin/products/status/', views.admin_products_status, name='admin_products_status'),
    path('admin/products/check-name/', views.admin_check_product_name, name='admin_check_product_name'),
    path('admin/products/image/<int:product_id>/', views.admin_product_image, name='admin_product_image'),

    # route pour les employe
    path('employe/dashboard/', views.employee_dashboard, name='dashboard_employe'),
    path('employe/products/create/', views.employe_products_create, name='employe_products_create'),

    # Sitemap
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),

    path('robots.txt', RobotsTxtView.as_view(), name='robots_txt'),

]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),
    path('cart/', views.cart, name='cart'),
    path('add_to_cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('buy_now/<int:product_id>/', views.buy_now, name='buy_now'),
    path('remove_from_cart/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('order_history/', views.order_history, name='order_history'),
    path('order/delete/<int:order_id>/', views.cancel_order, name='cancel_order'),
    path("login/", views.user_login, name="login"),
    path('logout/', views.user_logout, name='logout'),
    path("register/", views.register, name="register"),
    path('contact_info/', views.contact_info, name='contact_info'),
    path('checkout/', views.checkout, name='checkout'),
    
]
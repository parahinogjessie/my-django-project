from django.contrib import admin
from .models import Product, Cart, CartItem, Order
from django.contrib.auth.models import User

admin.site.register(User)
admin.site.register(Product)
admin.site.register(Order)
admin.site.register(Cart)
admin.site.register(CartItem)

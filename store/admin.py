from django.contrib import admin
from .models import Product, Cart, CartItem, Order, Profile

# Safe way to unregister only if registered
try:
    admin.site.unregister(Product)
except admin.sites.NotRegistered:
    pass  # Ignore if Product was not registered yet

# Custom ProductAdmin
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'original_price', 'added_by', 'is_approved', 'created_at')
    list_filter = ('is_approved', 'added_by')
    search_fields = ('name', 'description', 'added_by__username')
    ordering = ('-created_at',)

# Register Product with the custom admin
admin.site.register(Product, ProductAdmin)

# Register other models normally
admin.site.register(Order)
admin.site.register(Cart)
admin.site.register(CartItem)
admin.site.register(Profile)
from django.shortcuts import render, redirect, get_object_or_404
from .models import Product, Cart, CartItem, Order
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm 
from django.contrib.auth import login, logout, authenticate
from django.core.cache import cache
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages

def home(request):
    products = Product.objects.all()
    return render(request, 'store/home.html',{'products': products})

@login_required(login_url='login')
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    cart, _ = Cart.objects.get_or_create(user=request.user)

    cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)

    if not created:
        cart_item.quantity += 1
        cart_item.save()

    return redirect('cart')

@login_required(login_url='login')
def cart(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    cart_items = CartItem.objects.filter(cart=cart)

    for item in cart_items:
        item.subtotal = item.product.discount_price * item.quantity

    total = sum(item.product.discount_price * item.quantity for item in cart_items)

    return render(request, 'store/cart.html', {'cart_items': cart_items, 'total': total})

@login_required(login_url='login')
def remove_from_cart(request, product_id):
    cart = get_object_or_404(Cart, user=request.user)

    cart_item = get_object_or_404(
        CartItem, cart=cart, product_id=product_id
    )
    cart_item.delete()
    return redirect('cart')

@login_required(login_url ='login')
def order(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == "POST":
        quantity = int(request.POST.get("quantity", 1))
        total_price = product.discount_price * quantity

        Order.objects.create(
            user=request.user,
            product=product,
            quantity=quantity,
            total_price=total_price,
        )

        return redirect('order_history')
    return render(request, 'store/order.html', {'product': product})

@login_required(login_url='login')
def checkout(request):
    cart_items = CartItem.objects.filter(cart__user=request.user)

    total = 0
    for item in cart_items:
        item.subtotal = item.product.discount_price * item.quantity
        total += item.subtotal

    if request.method == "POST":
        selected_ids = request.POST.getlist("cart_item_ids")
        if not selected_ids:
            # No items selected
            return redirect('cart')

        for item_id in selected_ids:
            item = CartItem.objects.get(id=item_id, cart__user=request.user)
            Order.objects.create(
                user=request.user,
                product=item.product,
                quantity=item.quantity,
                total_price=item.product.discount_price * item.quantity
            )
            item.delete()  # remove from cart after ordering

        return redirect('order_history')

    return render(request, 'store/checkout.html', {
        'cart_items': cart_items,
        'total': total
    })

@login_required(login_url='login')
def order_history(request):

    orders = Order.objects.filter(user=request.user)

    return render(request, 'store/order_history.html', {
        'orders': orders
    })

@login_required(login_url='login')
def delete_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order.delete()
    return redirect('order_history')

MAX_LOGIN_ATTEMPTS = 3
LOGIN_COOLDOWN = 120
MAX_REG_PER_DAY = 3

def get_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip

def user_login(request):
    cooldown = 0

    # If user is already logged in, redirect to home
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        # Cache key per username to track login attempts
        cache_key = f"login_attempts_{username}"
        attempts = cache.get(cache_key, {"count": 0, "time": timezone.now()})

        # Check if user is in cooldown
        if attempts["count"] >= MAX_LOGIN_ATTEMPTS:
            elapsed = (timezone.now() - attempts["time"]).total_seconds()
            if elapsed < LOGIN_COOLDOWN:
                cooldown = int(LOGIN_COOLDOWN - elapsed)
                messages.error(request, f"Too many attempts. Try again in {cooldown} seconds.")
                return render(request, "store/login.html", {"cooldown": cooldown})
            else:
                # Reset attempts after cooldown
                attempts = {"count": 0, "time": timezone.now()}

        # Try to authenticate
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            cache.delete(cache_key)  # clear attempts after successful login
            messages.success(request, "Logged in successfully!")
            return redirect("home")
        else:
            # Increment attempts on failure
            attempts["count"] += 1
            attempts["time"] = timezone.now()
            cache.set(cache_key, attempts, timeout=LOGIN_COOLDOWN)
            messages.error(request, "Invalid username or password.")

    return render(request, "store/login.html", {"cooldown": cooldown})

def register(request):
    ip = get_ip(request)
    cache_key = f"register_{ip}"
    data = cache.get(cache_key, {"count":0, "date": timezone.now().date()})

    # Reset count if day changed
    if data["date"] != timezone.now().date():
        data = {"count":0, "date": timezone.now().date()}

    # Block if over limit
    if data["count"] >= MAX_REG_PER_DAY:
        return render(request,"store/register.html",{"cooldown":1})  # disables form

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        confirm = request.POST.get("confirm_password")

        # Validation
        if len(username) < 15:
            return render(request,"store/register.html")
        if len(password) < 8 or not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
            return render(request,"store/register.html")
        if password != confirm:
            return render(request,"store/register.html")
        if User.objects.filter(username=username).exists():
            return render(request,"store/register.html")

        # Create user and login
        user = User.objects.create_user(username=username,password=password)
        login(request,user)

        # Increment count per IP
        data["count"] += 1
        cache.set(cache_key,data,timeout=86400)  # 1 day

        return redirect("home")  # redirect after success

    return render(request,"store/register.html",{"cooldown":0})

def user_logout(request):
    logout(request)
    return redirect('home')

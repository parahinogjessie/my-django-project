from django.shortcuts import render, redirect, get_object_or_404
from .models import Product, Cart, CartItem, Order, Profile
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm 
from django.contrib.auth import login, logout, authenticate
from django.core.cache import cache
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
from django.db import transaction
from .forms import ProductForm

def is_admin(user):
    return user.is_authenticated and user.is_superuser

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):

    total_products = Product.objects.count()
    total_orders = Order.objects.count()
    total_users = User.objects.count()

    recent_orders = Order.objects.all().order_by('-id')[:5]
    total_revenue = sum(order.total_price for order in Order.objects.all())

    context = {
        'total_products': total_products,
        'total_orders': total_orders,
        'total_users': total_users,
        'total_revenue': total_revenue,
        'recent_orders': recent_orders,
    }

    return render(request, "store/admin_dashboard.html", context)

@login_required
@user_passes_test(is_admin)
def all_orders(request):
    orders = Order.objects.select_related('user', 'product').order_by('-id')

    return render(request, 'store/all_orders.html', {
        'orders': orders
    })
def staff_check(user):
    return user.is_authenticated and user.is_staff and not user.is_superuser

@login_required
@user_passes_test(is_admin)
def update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if request.method == "POST":
        new_status = request.POST.get("status")

        if new_status in ["pending", "shipped", "delivered"]:
            order.status = new_status
            order.save()

    return redirect('all_orders')

# Staff adds product
@login_required
@user_passes_test(staff_check)
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.added_by = request.user
            product.status = 'pending'
            product.save()
            return redirect('staff_dashboard')  # Optional: your staff dashboard
    else:
        form = ProductForm()
    return render(request, 'store/add_product.html', {'form': form})

@login_required
@user_passes_test(staff_check)
def staff_dashboard(request):
    # get all products added by this staff user
    products = Product.objects.filter(added_by=request.user).order_by('-created_at')
    return render(request, 'store/staff_dashboard.html', {'products': products})

@login_required
@user_passes_test(staff_check)
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, added_by=request.user)

    # Only allow editing if not approved yet
    if product.status == 'approved':
        return redirect('staff_dashboard')

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            return redirect('staff_dashboard')
    else:
        form = ProductForm(instance=product)
    
    return render(request, 'store/edit_product.html', {'form': form, 'product': product})

@login_required
@user_passes_test(staff_check)
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, added_by=request.user)

    # Only allow deletion if not approved yet
    if product.status == 'approved':
        return redirect('staff_dashboard')

    if request.method == 'POST':
        product.delete()
        return redirect('staff_dashboard')

    return render(request, 'store/delete_product_confirm.html', {'product': product})

# Admin approves product
@login_required
@user_passes_test(is_admin)
def approve_products(request):
    pending_products = Product.objects.filter(status='pending')

    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        action = request.POST.get('action')

        product = get_object_or_404(Product, id=product_id)

        # APPROVE
        if action == "approve":
            product.status = "approved"

        # REJECT
        elif action == "reject":
            product.status = "rejected"

        product.save()
        return redirect('approve_products')

    return render(request, 'store/approve_products.html', {
        'products': pending_products
    })

# Show approved products to customers
def product_list(request):
    products = Product.objects.filter(status='approved')
    return render(request, 'store/product_list.html', {'products': products})

def home(request):
    products = Product.objects.filter(status='approved')
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

    # compute subtotal
    for item in cart_items:
        item.subtotal = (item.product.discount_price or item.product.original_price) * item.quantity

    total = sum(item.subtotal for item in cart_items)

    if request.method == "POST":
        selected_ids = request.POST.getlist("cart_item_ids")

        if not selected_ids:
            return redirect('cart')  # nothing selected

        # SAVE selected items to session
        request.session["selected_cart_items"] = selected_ids

        return redirect('checkout')

    return render(request, 'store/cart.html', {
        'cart_items': cart_items,
        'total': total
    })

@login_required(login_url='login')
def remove_from_cart(request, product_id):
    cart = get_object_or_404(Cart, user=request.user)

    cart_item = get_object_or_404(
        CartItem, cart=cart, product_id=product_id
    )
    cart_item.delete()
    return redirect('cart')

@login_required(login_url='login')
def checkout(request):
    if request.method == "POST":
        # get selected cart items
        selected_ids = request.POST.getlist('cart_item_ids')
        if not selected_ids:
            messages.error(request, "Please select at least one item to checkout.")
            return redirect('cart')

        cart_items = CartItem.objects.filter(id__in=selected_ids, cart__user=request.user)

        total = 0
        for item in cart_items:
            price = item.product.discount_price if item.product.discount_price else item.product.original_price
            item.subtotal = price * item.quantity
            total += item.subtotal

        profile = getattr(request.user, 'profile', None)

        if 'place_order' in request.POST:
            full_name = request.POST.get('full_name')
            mobile = request.POST.get('mobile')
            address = request.POST.get('address')

            # update profile info
            if profile:
                profile.full_name = full_name
                profile.mobile = mobile
                profile.address = address
                profile.save()

            # create orders
            for item in cart_items:
                price = item.product.discount_price if item.product.discount_price else item.product.original_price
                Order.objects.create(
                    user=request.user,
                    product=item.product,
                    quantity=item.quantity,
                    total_price=price * item.quantity
                )
                item.delete()

            return redirect('order_history')

        return render(request, 'store/checkout.html', {
            'cart_items': cart_items,
            'total': total,
            'profile': profile
        })

    return redirect('cart')  # if no POST, go back to cart

@login_required(login_url='login')
def buy_now(request, product_id):
    # Get the product
    product = get_object_or_404(Product, id=product_id)
    
    # Get or create user's profile
    profile = getattr(request.user, 'profile', None)

    if request.method == "POST":
        quantity = int(request.POST.get("quantity", 1))
        price = product.discount_price if product.discount_price else product.original_price

        # Update or create profile info
        full_name = request.POST.get('full_name')
        mobile = request.POST.get('mobile')
        address = request.POST.get('address')
        if profile:
            profile.full_name = full_name
            profile.mobile = mobile
            profile.address = address
            profile.save()
        else:
            profile = Profile.objects.create(
                user=request.user,
                full_name=full_name,
                mobile=mobile,
                address=address
            )

        # Create the order
        Order.objects.create(
            user=request.user,
            product=product,
            quantity=quantity,
            total_price=price * quantity
        )

        return redirect('order_history')

    # GET request → show Buy Now page
    return render(request, 'store/buy_now.html', {
        'product': product,
        'profile': profile
    })

@login_required(login_url='login')
def order_history(request):

    orders = Order.objects.filter(user=request.user)

    return render(request, 'store/order_history.html', {
        'orders': orders
    })

@login_required(login_url='login')
def cancel_order(request, order_id):
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

            # ✅ ROLE-BASED REDIRECT (ADMIN / STAFF / USER)
            if user.is_superuser:
                return redirect("admin_dashboard")
            elif user.is_staff:
                return redirect("staff_dashboard")
            else:
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

from .models import Profile, ContactMessage

@login_required(login_url='login')
def contact_us(request):
    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        profile = None

    if request.method == "POST":
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        mobile = request.POST.get('mobile')
        address = request.POST.get('address')
        message = request.POST.get('message')

        # Save/update profile
        if profile:
            profile.full_name = full_name
            profile.mobile = mobile
            profile.address = address
            profile.save()
        else:
            Profile.objects.create(
                user=request.user,
                full_name=full_name,
                mobile=mobile,
                address=address
            )

        # Save message
        ContactMessage.objects.create(
            user=request.user,
            full_name=full_name,
            email=email,
            mobile=mobile,
            address=address,
            message=message
        )

        # Update user email
        request.user.email = email
        request.user.save()

        messages.success(request, "Message sent successfully!")
        return redirect('home')

    return render(request, 'store/contact_us.html', {'profile': profile})
from django.shortcuts import render
from django.shortcuts import redirect
from .models import Product

def home(request):
    products = Product.objects.all()
    return render(request, 'store/home.html',{'products': products})

#Handles the add to cart
def add_to_cart(request, product_id):
   cart = request.session.get('cart', [])
   cart.append(product_id)
   request.session['cart'] = cart   
   return redirect('home')

def cart(request):
    cart = request.session.get('cart', [])
    products = Product.objects.filter(id__in=cart)
    return render(request, 'store/cart.html', {'products': products})

def remove_from_cart(request, product_id):
    cart = request.session.get('cart', [])
    if product_id in cart:
        cart.remove(product_id)
        request.session['cart'] = cart
        return redirect('cart')
    

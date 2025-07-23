from django.shortcuts import render
from django.shortcuts import render

from .models import Product

import logging
logger = logging.getLogger(__name__)

def product(request):
    cat = request.GET.get('cat', 'men')
    if cat=='men':
        heading="men's fashion"
        description="Discover stylish clothing for the modern"         
    elif cat == 'women':
        heading="Women's Fashion"
        description="Discover the latest trends in women's clothing"  
    elif cat == 'kids':
        heading="kid's Fashion"
        description="fun and comfortable clothing for children" 
    elif cat == 'furniture':
        heading="Furniture" 
        description="Beautiful furniture for your home"        
    elif cat == 'electronics':
        heading="Electronics"  
        description="Latest gadgets and technology"
    elif cat == 'sportswear':
        heading="Sportswear"  
        description="Latest gadgets and technology"
    
    
        
    products = Product.objects.filter(category=cat)
    logger.debug(f"Products: {list(products.values())}")
    return render(request, "product.html", {"products": products, "heading": heading , "description": description})


def login(request):
    return render(request, 'login.html')

def profile(request):
    return render(request, 'profile.html')

def signup(request):
    return render(request, 'signup.html')

def wishlist(request):
    return render(request, 'wishlist.html')

def yourorders(request):    
    return render(request, 'yourorders.html')

def clear_data(request):
    return render(request, 'clear_data.html')

def home(request):
    return render(request, 'home.html')


def cart(request):
    return render(request, 'cart.html')
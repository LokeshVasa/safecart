from django.shortcuts import render
from django.shortcuts import render

from .models import Product

import logging
logger = logging.getLogger(__name__)

def home(request):
    return render(request, 'home.html')

def kids(request):
    products = Product.objects.filter(category='kids')
    logger.debug(f"Products: {list(products.values())}")
    return render(request, "kids.html", {"products": products})


def cart(request):
    return render(request, 'cart.html')

def men(request):
    products = Product.objects.filter(category='men')
    logger.debug(f"Products: {list(products.values())}")
    return render(request, "men.html", {"products": products})


def women(request):
    products = Product.objects.filter(category='women')
    logger.debug(f"Products: {list(products.values())}")
    return render(request, "women.html", {"products": products})


def electronics(request):
    products = Product.objects.filter(category='electronics')
    logger.debug(f"Products: {list(products.values())}")
    return render(request, "electronics.html", {"products": products})
def furniture(request):
    products = Product.objects.filter(category='furniture')
    logger.debug(f"Products: {list(products.values())}")
    return render(request, "furniture.html", {"products": products})

def sportswear(request):
    products = Product.objects.filter(category='sportswear')
    logger.debug(f"Products: {list(products.values())}")
    return render(request, "sportswear.html", {"products": products})



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
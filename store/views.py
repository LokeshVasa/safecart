from django.shortcuts import render
from .models import Product, Category
import logging
from django.shortcuts import get_object_or_404


logger = logging.getLogger(__name__)

def product(request):
    category = request.GET.get('category', 'men')
    category_object = get_object_or_404(Category, category=category)
    products = Product.objects.filter(category=category)
    heading = category_object.heading
    description = category_object.description
    

    return render(request, "product.html", {"products": products,"heading": heading,"description": description})

def home(request):
    categories = Category.objects.all()
    return render(request, 'home.html', {"categories": categories})

def login(request):
    return render(request, 'login.html')

def profile(request):
    return render(request, 'profile.html')

def signup(request):
    return render(request, 'signup.html')

def wishlist(request):
    category = request.GET.get('category', 'men')
    products = Product.objects.filter(category=category)
    return render(request, 'cart.html', {"products": products})

def yourorders(request):
    return render(request, 'yourorders.html')

def clear_data(request):
    return render(request, 'clear_data.html')

def cart(request):
    category = request.GET.get('category', 'men')
    products = Product.objects.filter(category=category)
    return render(request, 'cart.html', {"products": products})

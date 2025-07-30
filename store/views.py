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
    return render(request, 'login')

def profile(request):
    return render(request, 'profile')

def signup(request):
    return render(request, 'signup')

def wishlist(request):
    return render(request, 'wishlist.html')

def yourorders(request):
    return render(request, 'yourorders')

def clear_data(request):
    return render(request, 'clear_data')

def cart(request):
    return render(request, 'cart.html')

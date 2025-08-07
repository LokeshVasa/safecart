from django.shortcuts import render,redirect
from .models import Product, Category, Cart, Wishlist
import logging
from django.shortcuts import get_object_or_404
from .forms import RegisterForm, ForgotPasswordForm
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone
from django.urls import reverse
from .models import *




logger = logging.getLogger(__name__)

@login_required
def product(request):
    category = request.GET.get('category', 'men')
    category_object = get_object_or_404(Category, category=category)
    products = Product.objects.filter(category=category)
    heading = category_object.heading
    description = category_object.description
    

    return render(request, "product.html", {"products": products,"heading": heading,"description": description})

@login_required
def home(request):
    categories = Category.objects.all()
    return render(request, 'home.html', {"categories": categories})


@login_required
def profile(request):
    return render(request, 'profile.html')


@login_required
def wishlist_view(request):
    user = request.user
    wishlist_items = Wishlist.objects.filter(user=user).select_related('product')
    return render(request, 'wishlist.html', {'wishlist_items': wishlist_items})



@login_required
def yourorders(request):
    return render(request, 'yourorders.html')

def clear_data(request):
    return render(request, 'clear_data.html')


@login_required
def cart(request):
    user = request.user
    cart_items = (
        Cart.objects.filter(user=user)
        .values('product')  # group by product
        .annotate(quantity=Count('product')) 
        .order_by('product')
    )

    # Fetch full product info
    products_with_quantity = []
    for item in cart_items:
        product = Product.objects.get(id=item['product'])
        products_with_quantity.append({
            'product': product,
            'quantity': item['quantity']
        })

    return render(request, 'cart.html', {'cart_items': products_with_quantity})



# Auth Files

def RegisterView(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome, {user.first_name}! Your account is ready.")
            return redirect('home')
    else:
        form = RegisterForm()

    return render(request, 'registration/signup.html', {'form': form})


def LoginView(request):
    if request.method == "POST":
        identifier = request.POST.get("username")  # Can be username or email
        password = request.POST.get("password")

        user = None

        if User.objects.filter(email=identifier).exists():
            try:
                user_obj = User.objects.get(email=identifier)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                pass
        else:
            user = authenticate(request, username=identifier, password=password)

        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, "Invalid login credentials")
            return redirect('login')

    return render(request, 'registration/login.html')

def LogoutView(request):
    logout(request)
    return redirect('login')


def ForgotPassword(request):

    if request.method == "POST":
        email = request.POST.get('email')

        try:
            user = User.objects.get(email=email)

            new_password_reset = PasswordReset(user=user)
            new_password_reset.save()

            password_reset_url = reverse('reset-password', kwargs={'reset_id': new_password_reset.reset_id})

            full_password_reset_url = f'{request.scheme}://{request.get_host()}{password_reset_url}'

            email_body = f'Reset your password using the link below:\n\n\n{full_password_reset_url}'
        
            email_message = EmailMessage(
                'Reset your password', # email subject
                email_body,
                settings.EMAIL_HOST_USER, # email sender
                [email] # email  receiver 
            )

            email_message.fail_silently = True
            email_message.send()

            return redirect('password-reset-sent', reset_id=new_password_reset.reset_id)

        except User.DoesNotExist:
            messages.error(request, f"No user with email '{email}' found")
            return redirect('forgot-password')

    form = ForgotPasswordForm()

    return render(request, 'registration/forgot_password.html', {'form': form})


def PasswordResetSent(request, reset_id):

    if PasswordReset.objects.filter(reset_id=reset_id).exists():
        return render(request, 'registration/password_reset_sent.html')
    else:
        # redirect to forgot password page if code does not exist
        messages.error(request, 'Invalid reset id')
        return redirect('forgot-password')

def ResetPassword(request, reset_id):

    try:
        password_reset_id = PasswordReset.objects.get(reset_id=reset_id)

        if request.method == "POST":
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirm_password')

            passwords_have_error = False

            if password != confirm_password:
                passwords_have_error = True
                messages.error(request, 'Passwords do not match')

            if len(password) < 5:
                passwords_have_error = True
                messages.error(request, 'Password must be at least 5 characters long')

            expiration_time = password_reset_id.created_when + timezone.timedelta(minutes=10)

            if timezone.now() > expiration_time:
                passwords_have_error = True
                messages.error(request, 'Reset link has expired')

                password_reset_id.delete()

            if not passwords_have_error:
                user = password_reset_id.user
                user.set_password(password)
                user.save()

                password_reset_id.delete()

                messages.success(request, 'Password reset. Proceed to login')
                return redirect('login')
            else:
                # redirect back to password reset page and display errors
                return redirect('reset-password', reset_id=reset_id)

    
    except PasswordReset.DoesNotExist:
        
        # redirect to forgot password page if code does not exist
        messages.error(request, 'Invalid reset id')
        return redirect('forgot-password')

    return render(request, 'registration/reset_password.html')


@login_required
def add_to_cart(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        product = get_object_or_404(Product, id=product_id)
        user = request.user

        # Check if already in cart
        cart_item, created = Cart.objects.get_or_create(user=user, product=product)

        if created:
            messages.success(request, f"{product.name} added to cart.")
        else:
            messages.info(request, f"{product.name} is already in your cart.")

        # Redirect to the same page or cart page
        return redirect(request.META.get('HTTP_REFERER', 'home'))
    else:
        return redirect('home')



@login_required
def add_to_wishlist(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        product = get_object_or_404(Product, id=product_id)
        user = request.user

        item, created = Wishlist.objects.get_or_create(user=user, product=product)

        if created:
            messages.success(request, f"{product.name} added to your wishlist.")
        else:
            messages.info(request, f"{product.name} is already in your wishlist.")

        return redirect(request.META.get('HTTP_REFERER', 'home'))
    return redirect('home')

from django.shortcuts import render, redirect, get_object_or_404
from .models import Product, Category, Cart, Wishlist, PasswordReset
import logging
from .forms import RegisterForm, ForgotPasswordForm
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone
from django.urls import reverse
from django.db.models import Count
from django.http import JsonResponse
from django.template.loader import render_to_string
from decimal import Decimal, ROUND_HALF_UP
from .models import Address
from .forms import AddressForm
from .models import Order, OrderItem
import uuid
from datetime import timedelta
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, permission_required


logger = logging.getLogger(__name__)

# -------------------- PRODUCT & HOME --------------------

def product(request):
    category = request.GET.get('category', 'men')
    category_object = get_object_or_404(Category, category=category)
    products = Product.objects.filter(category=category)
    return render(request, "product.html", {
        "products": products,
        "heading": category_object.heading,
        "description": category_object.description,
        "category": category
    })

def home(request):
    categories = Category.objects.all()
    return render(request, 'home.html', {"categories": categories})

# -------------------- PROFILE & WISHLIST --------------------

@login_required
def profile(request):
    return render(request, 'profile.html')

@login_required
def wishlist_view(request):
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product')
    return render(request, 'wishlist.html', {'wishlist_items': wishlist_items})

@login_required
def yourorders(request):
    return render(request, 'yourorders.html')

def clear_data(request):
    return render(request, 'clear_data.html')

@login_required
@require_POST
def change_quantity(request, product_id):
    """
    Handle both increase and decrease of cart item quantity.
    Expects POST param: action = 'increase' or 'decrease'
    """
    action = request.POST.get("action")
    cart_item = get_object_or_404(Cart, user=request.user, product_id=product_id)

    if action == "increase":
        cart_item.quantity += 1
        cart_item.save()
    elif action == "decrease":
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
        else:
            cart_item.delete()
    else:
        return JsonResponse({"error": "Invalid action"}, status=400)

    # Recalculate totals
    subtotal = sum(item.product.price * item.quantity for item in Cart.objects.filter(user=request.user))
    tax = (subtotal * Decimal("0.10")).quantize(Decimal("0.01"))
    shipping = Decimal("50.00") if subtotal > 0 else Decimal("0.00")
    total = subtotal + tax + shipping

    response = {
        "updated_product_id": product_id,
        "new_qty": cart_item.quantity if cart_item.id else 0,
        "subtotal": str(subtotal),
        "tax": str(tax),
        "shipping": str(shipping),
        "total": str(total),
    }

    # HTMX support
    if request.headers.get("HX-Request"):
        response["flash_html"] = render_to_string("flash_messages.html", {}, request=request)

    return JsonResponse(response)

@login_required
def cart(request):
    cart_items = Cart.objects.filter(user=request.user).select_related("product")
    subtotal = sum(item.product.price for item in cart_items)
    tax = round(Decimal(subtotal) * Decimal("0.10"), 2)
    shipping = Decimal("50.00") if subtotal > 0 else Decimal("0.00")
    total = subtotal + tax + shipping

    # last address for prefill
    last_address = Address.objects.filter(user=request.user).last()
    form = AddressForm(instance=last_address)

    # all addresses for modal
    all_addresses = Address.objects.filter(user=request.user).order_by("-id")

    context = {
        "cart_items": cart_items,
        "subtotal": subtotal,
        "tax": tax,
        "shipping": shipping,
        "total": total,
        "form": form,
        "all_addresses": all_addresses,
    }
    return render(request, "cart.html", context)

# -------------------- AUTH --------------------

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
        identifier = request.POST.get("username")
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
                # Role-based redirect
            if user.is_superuser or user.groups.filter(name='Admin').exists():
                return redirect('admin_dashboard')
            elif user.groups.filter(name='DeliveryAgent').exists():
                return redirect('delivery_dashboard')
            else:  # Buyer or new user
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
                'Reset your password',
                email_body,
                settings.EMAIL_HOST_USER,
                [email]
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
                return redirect('reset-password', reset_id=reset_id)

    except PasswordReset.DoesNotExist:
        messages.error(request, 'Invalid reset id')
        return redirect('forgot-password')

    return render(request, 'registration/reset_password.html')

# -------------------- CART / WISHLIST ACTIONS --------------------

@login_required
def add_to_cart(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        product = get_object_or_404(Product, id=product_id)
        cart_item, created = Cart.objects.get_or_create(user=request.user, product=product)
        if created:
            messages.success(request, f"{product.name} added to cart.")
        else:
            messages.info(request, f"{product.name} is already in your cart.")
        if request.headers.get("HX-Request"):
            cart_count = Cart.objects.filter(user=request.user).count()
            flash_html = render_to_string("flash_messages.html", {}, request=request)

            return JsonResponse({
                "cart_count": cart_count,
                "flash_html": flash_html
            })

        category = request.POST.get("category", "men")

        # this is just fallback. We are not using redirect in success case
        return redirect(f"{reverse('product')}?category={category}")

    # this is just fallback. We are not using redirect in success case
    return redirect("home")

@login_required
def add_to_wishlist(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        product = get_object_or_404(Product, id=product_id)

        wishlist_item, created = Wishlist.objects.get_or_create(user=request.user, product=product)
        if created:
            messages.success(request, f"{product.name} added to wishlist.")
        else:
            messages.info(request, f"{product.name} is already in your wishlist.")

        # If request is via HTMX → return JSON instead of redirect
        if request.headers.get("HX-Request"):
            wishlist_count = Wishlist.objects.filter(user=request.user).count()
            flash_html = render_to_string("flash_messages.html", {}, request=request)

            return JsonResponse({
                "wishlist_count": wishlist_count,
                "flash_html": flash_html
            })

        category = request.POST.get("category", "men")

        # fallback redirect if not HTMX
        return redirect(f"{reverse('product')}?category={category}")

    return redirect("home")

@login_required
def remove_from_cart(request, product_id):
    """Remove an item from cart (HTMX-aware)."""
    Cart.objects.filter(user=request.user, product_id=product_id).delete()
    messages.success(request, "Item removed from cart.")

    if request.headers.get("HX-Request"):
        cart_count = Cart.objects.filter(user=request.user).count()
        subtotal, tax, shipping, total = calculate_cart_totals(request.user)
        flash_html = render_to_string("flash_messages.html", {}, request=request)

        return JsonResponse({
            "cart_count": cart_count,
            "flash_html": flash_html,
            "removed_product_id": product_id,
            "subtotal": str(subtotal),
            "tax": str(tax),
            "shipping": str(shipping),
            "total": str(total),
            "cart_empty": cart_count == 0,
        })

    return redirect(request.META.get('HTTP_REFERER', 'cart'))



@login_required
def move_to_wishlist(request, product_id):
    """Move a cart item into wishlist (HTMX-aware)."""
    product = get_object_or_404(Product, id=product_id)
    Wishlist.objects.get_or_create(user=request.user, product=product)
    Cart.objects.filter(user=request.user, product=product).delete()
    messages.success(request, f"{product.name} moved to wishlist.")

    if request.headers.get("HX-Request"):
        wishlist_count = Wishlist.objects.filter(user=request.user).count()
        cart_count = Cart.objects.filter(user=request.user).count()
        subtotal, tax, shipping, total = calculate_cart_totals(request.user)
        flash_html = render_to_string("flash_messages.html", {}, request=request)

        return JsonResponse({
            "wishlist_count": wishlist_count,
            "cart_count": cart_count,
            "flash_html": flash_html,
            "moved_product_id": product_id,
            "subtotal": str(subtotal),
            "tax": str(tax),
            "shipping": str(shipping),
            "total": str(total),
            "cart_empty": cart_count == 0,
        })

    return redirect(request.META.get('HTTP_REFERER', 'cart'))


def calculate_cart_totals(user):
    cart_items = (
        Cart.objects.filter(user=user)
        .values('product')
        .annotate(quantity=Count('product'))
    )

    subtotal = Decimal("0.00")
    for item in cart_items:
        product = Product.objects.get(id=item['product'])
        subtotal += product.price * item['quantity']

    tax = (subtotal * Decimal("0.10")).quantize(Decimal("0.01"))
    shipping = Decimal("50.00") if subtotal > 0 else Decimal("0.00")
    total = subtotal + tax + shipping

    return subtotal, tax, shipping, total


@login_required
def remove_from_wishlist(request, product_id):
    """Remove a product from wishlist (HTMX-aware)."""
    Wishlist.objects.filter(user=request.user, product_id=product_id).delete()
    messages.success(request, "Item removed from wishlist.")

    if request.headers.get("HX-Request"):
        wishlist_count = Wishlist.objects.filter(user=request.user).count()
        flash_html = render_to_string("flash_messages.html", {}, request=request)

        return JsonResponse({
            "wishlist_count": wishlist_count,
            "flash_html": flash_html,
            "removed_product_id": product_id,   
        })

    return redirect(request.META.get("HTTP_REFERER", "wishlist"))


@login_required
def move_to_cart(request, product_id):
    """Move a wishlist item into cart (HTMX-aware)."""
    product = get_object_or_404(Product, id=product_id)
    Cart.objects.get_or_create(user=request.user, product=product)
    Wishlist.objects.filter(user=request.user, product=product).delete()
    messages.success(request, f"{product.name} moved to cart.")

    if request.headers.get("HX-Request"):
        cart_count = Cart.objects.filter(user=request.user).count()
        wishlist_count = Wishlist.objects.filter(user=request.user).count()
        flash_html = render_to_string("flash_messages.html", {}, request=request)

        return JsonResponse({
            "cart_count": cart_count,
            "wishlist_count": wishlist_count,
            "flash_html": flash_html,
            "moved_product_id": product_id,   # 🔑 so JS removes card
        })

    return redirect(request.META.get("HTTP_REFERER", "wishlist"))

@login_required
def save_address(request):
    """Handles new address submissions separately."""
    if request.method == "POST":
        form = AddressForm(request.POST)
        if form.is_valid():
            addr_data = form.cleaned_data

            # Prevent duplicates
            exists = Address.objects.filter(
                user=request.user,
                street=addr_data['street'],
                city=addr_data['city'],
                state=addr_data['state'],
                pincode=addr_data['pincode']
            ).exists()

            if not exists:
                addr = form.save(commit=False)
                addr.user = request.user
                addr.save()
                messages.success(request, "New shipping address added.")
            else:
                messages.info(request, "This address is already saved.")

    return redirect("cart")

@login_required
def proceed_to_checkout(request):
    cart_items = Cart.objects.filter(user=request.user).select_related('product')


    if not cart_items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect("cart")

    # Require address from form
    if request.method == "POST":
        form = AddressForm(request.POST)
        if form.is_valid():
            addr_data = form.cleaned_data

            address, created = Address.objects.get_or_create(
                user=request.user,
                street=addr_data['street'],
                city=addr_data['city'],
                state=addr_data['state'],
                pincode=addr_data['pincode']
            )
            if created:
                messages.success(request, "New shipping address added.")
        else:
            messages.error(request, "Please provide a valid shipping address.")
            return redirect("cart")
    else:
        messages.error(request, "Please submit a shipping address before checkout.")
        return redirect("cart")

    # Create the order
    order = Order.objects.create(
        user=request.user,
        address=address,
        payment_type="COD",
        token_value=str(uuid.uuid4()),
        expires_at=timezone.now() + timezone.timedelta(hours=1),
        status="Pending"
    )

    # Add order items
    for item in cart_items:
        OrderItem.objects.create(
        order=order,
        product=item.product,
        quantity=item.quantity,
        price=item.product.price
    )


    # Empty cart
    Cart.objects.filter(user=request.user).delete()

    messages.success(request, "Your order has been placed successfully!")
    return redirect("yourorders")


@login_required
def yourorders(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')

    # Prepare orders with items
    orders_with_details = []
    for order in orders:
        items = []
        for item in order.items.all():  # related_name='items' in OrderItem
            items.append({
                'name': item.product.name,
                'image': item.product.image,
                'quantity': item.quantity,
                'price': item.price,
            })
        total_amount = sum(i['price'] * i['quantity'] for i in items)
        expected_delivery = order.created_at + timedelta(days=5)  # example 5 days delivery
        orders_with_details.append({
            'id': order.id,
            'status': order.status,
            'date': order.created_at,
            'items': items,
            'total_amount': total_amount,
            'expected_delivery': expected_delivery,
            'address': order.address,
        })

    return render(request, 'yourorders.html', {'orders': orders_with_details})

@login_required
def sellerorders(request):
    # Adjust the filtering below for what a "seller" should see (e.g., all orders or only for their products)
    orders = Order.objects.all().order_by('-created_at')
    orders_with_details = []
    for order in orders:
        items = []
        for item in order.items.all():
            items.append({
                'name': item.product.name,
                'image': item.product.image,
                'quantity': item.quantity,
                'price': item.price,
            })
        total_amount = sum(i['price'] * i['quantity'] for i in items)
        expected_delivery = order.created_at + timedelta(days=5)
        orders_with_details.append({
            'id': order.id,
            'status': order.status,
            'date': order.created_at,
            'items': items,
            'total_amount': total_amount,
            'expected_delivery': expected_delivery,
            'pincode': order.address.pincode,
            'token_': order.token_value,  # Ensure your Order model has token_value
        })
    return render(request, 'sellerorders.html', {'orders': orders_with_details})

@login_required
@permission_required('store.can_perform_admin_actions', raise_exception=True)
def make_delivery_agent(request, user_id):
    user = get_object_or_404(User, id=user_id)
    delivery_group, _ = Group.objects.get_or_create(name='DeliveryAgent')
    buyer_group, _ = Group.objects.get_or_create(name='Buyer')

    if delivery_group in user.groups.all():
        user.groups.remove(delivery_group)
        user.groups.add(buyer_group)
        messages.success(request, f"{user.username} is now a Buyer.")
    else:
        user.groups.remove(buyer_group)
        user.groups.add(delivery_group)
        messages.success(request, f"{user.username} is now a Delivery Agent.")

    return redirect('admin_dashboard')


@login_required
@permission_required('store.can_perform_admin_actions', raise_exception=True)
def admin_dashboard(request):
    total_users = User.objects.filter(is_superuser=False).count()
    buyer_group, _ = Group.objects.get_or_create(name='Buyer')
    delivery_group, _ = Group.objects.get_or_create(name='DeliveryAgent')
    total_buyers = buyer_group.user_set.count()
    total_delivery_agents = delivery_group.user_set.count()
    total_products = Product.objects.count()
    total_orders = Order.objects.count()

    users = User.objects.filter(is_superuser=False).order_by('id')
    users_info = [
        {'user': u, 'is_delivery': delivery_group in u.groups.all()} for u in users
    ]

    context = {
        'total_users': total_users,
        'total_buyers': total_buyers,
        'total_delivery_agents': total_delivery_agents,
        'total_products': total_products,
        'total_orders': total_orders,
        'users_info': users_info,
    }
    return render(request, 'dashboard/admin_dashboard.html', context)


@login_required
@permission_required('store.can_deliver_order', raise_exception=True)
def delivery_dashboard(request):
    orders = Order.objects.all()
    return render(request, 'dashboard/delivery_dashboard.html', {'orders': orders})


@login_required
@permission_required('store.can_deliver_order', raise_exception=True)
def mark_order_delivered(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order.status = 'Delivered'
    order.save()
    messages.success(request, f"Order {order.id} marked as delivered.")
    return redirect('delivery_dashboard')


def dashboard_redirect(request):
    user = request.user
    if user.is_superuser or user.groups.filter(name='Admin').exists():
        return redirect('admin_dashboard')
    elif user.groups.filter(name='DeliveryAgent').exists():
        return redirect('delivery_dashboard')
    else:
        return redirect('home')
    
@login_required
@permission_required('store.can_perform_admin_actions', raise_exception=True)
def manage_users(request):
    users = User.objects.filter(is_superuser=False)
    delivery_group, _ = Group.objects.get_or_create(name='DeliveryAgent')
    buyer_group, _ = Group.objects.get_or_create(name='Buyer')

    users_info = [
        {'user': u, 'is_delivery': delivery_group in u.groups.all()}
        for u in users
    ]

    context = {
        'users_info': users_info,
        'total_users': users.count(),
        'total_buyers': buyer_group.user_set.count(),
        'total_delivery_agents': delivery_group.user_set.count(),
        'total_products': Product.objects.count(),
        'total_orders': Order.objects.count(),
    }
    return render(request, 'dashboard/admin_dashboard.html', context)

def delivery_order_detail(request):
    order_id = request.GET.get('order-id')
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'dashboard/delivery_order_detail.html', {'order': order})
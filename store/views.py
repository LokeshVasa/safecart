from django.shortcuts import render, redirect, get_object_or_404
from .models import Product, Cart, Wishlist
import logging
from .forms import RegisterForm, ForgotPasswordForm
from django.contrib.auth import login, logout
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse
from django.db.models import Count, Q
from django.http import JsonResponse, HttpResponseForbidden
from django.template.loader import render_to_string
from decimal import Decimal, ROUND_HALF_UP
from .models import Address
from .forms import AddressForm
from .models import Order, OrderItem, DeliveryAgent, OrderCallSession, OrderCallSignal
import uuid
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, permission_required
from .utils import geocode_address
from geopy.geocoders import Nominatim
from django.db import IntegrityError
from .services import (
    AuthServiceError,
    DeliveryAccessError,
    DeliveryQRScanError,
    OTPAccessError,
    OTPValidationError,
    ProfileUpdateError,
    authenticate_user_by_identifier,
    build_home_context,
    build_product_page_context,
    build_customer_orders_context,
    build_delivery_comparison_context,
    build_delivery_dashboard_context,
    build_security_logs_context,
    build_security_overview_context,
    build_seller_orders_context,
    claim_order_from_token,
    create_password_reset_request,
    get_order_otp_payload,
    get_order_security_snapshot,
    log_security_event,
    get_or_create_order_otp_payload,
    get_post_login_redirect_name,
    password_reset_exists,
    register_buyer_user,
    remove_profile_photo,
    reset_password_with_token,
    update_profile_photo,
    validate_delivery_agent_order_access,
    verify_order_otp as verify_order_otp_service,
)
import json
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)

# -------------------- PRODUCT & HOME --------------------

def product(request):
    context = build_product_page_context(request.GET.get('category', 'men'))
    return render(request, "product.html", context)

def home(request):
    context = build_home_context()
    return render(request, 'home.html', context)

# -------------------- PROFILE & WISHLIST --------------------

@login_required
def profile(request):
    if request.method == "POST":
        if request.POST.get("action") == "remove_photo":
            remove_profile_photo(request.user)
            messages.success(request, "Profile photo removed.")
            return redirect("profile")

        try:
            update_profile_photo(request.user, request.FILES.get("profile_photo"))
        except ProfileUpdateError as exc:
            messages.error(request, str(exc))
            return redirect("profile")

        messages.success(request, "Profile photo updated successfully.")
        return redirect("profile")

    return render(request, 'profile.html')

@login_required
def wishlist_view(request):
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product')
    return render(request, 'wishlist.html', {'wishlist_items': wishlist_items})

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

    new_address_data = request.session.get("new_address_data")

    form = AddressForm(initial=new_address_data) if new_address_data else AddressForm()

    hide_confirm_button = True if new_address_data else False
    
    # all addresses for modal
    all_addresses = Address.objects.filter(user=request.user).order_by("-id")

    selected_address_confirmed = False
    if new_address_data:
        selected_address = Address.objects.filter(
            user=request.user,
            street=new_address_data.get("street", ""),
            city=new_address_data.get("city", ""),
            state=new_address_data.get("state", ""),
            pincode=new_address_data.get("pincode", "")
        ).first()
        selected_address_confirmed = bool(selected_address and selected_address.is_confirmed)

    return render(request,"cart.html", {
        "cart_items": cart_items,
        "subtotal": subtotal,
        "tax": tax,
        "shipping": shipping,
        "total": total,
        "form": form,
        "all_addresses": all_addresses,
        "hide_confirm_button": hide_confirm_button,
        "has_confirmed_address": selected_address_confirmed,
    })

# -------------------- AUTH --------------------

def RegisterView(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = register_buyer_user(form)
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

        user = authenticate_user_by_identifier(request, identifier, password)

        if user is not None:
            login(request, user)
            return redirect(get_post_login_redirect_name(user))
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
            password_reset = create_password_reset_request(
                email=email,
                scheme=request.scheme,
                host=request.get_host(),
            )
            return redirect('password-reset-sent', reset_id=password_reset.reset_id)
        except AuthServiceError as exc:
            messages.error(request, str(exc))
            return redirect('forgot-password')

    form = ForgotPasswordForm()
    return render(request, 'registration/forgot_password.html', {'form': form})

def PasswordResetSent(request, reset_id):
    if password_reset_exists(reset_id):
        return render(request, 'registration/password_reset_sent.html')
    else:
        messages.error(request, 'Invalid reset id')
        return redirect('forgot-password')

def ResetPassword(request, reset_id):
    try:
        if request.method == "POST":
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirm_password')
            result = reset_password_with_token(
                reset_id=reset_id,
                password=password,
                confirm_password=confirm_password,
            )

            if result["success"]:
                messages.success(request, 'Password reset. Proceed to login')
                return redirect('login')
            for error in result["errors"]:
                messages.error(request, error)
            return redirect('reset-password', reset_id=reset_id)

    except AuthServiceError:
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
    if request.method == "POST":
        form = AddressForm(request.POST)
        if form.is_valid():
            addr_data = form.cleaned_data

            address = Address.objects.filter(
                user=request.user,
                street=addr_data['street'],
                city=addr_data['city'],
                state=addr_data['state'],
                pincode=addr_data['pincode']
            ).first()

            if not address:
                address = form.save(commit=False)
                address.user = request.user
                address.is_confirmed = False
                address.save()

                #--Method 1: Geocode here--
                geocode_address_obj(address)

                messages.success(request, "Address saved. Please confirm the location on map.")
            else:
                messages.info(request, "Address already exists.")
    
    return redirect("cart")


def geocode_address_obj(address):
    geolocator = Nominatim(user_agent="safecart")
    full_address = f"{address.street}, {address.city}, {address.state}, {address.pincode}"
    location = geolocator.geocode(full_address)

    if location:
        address.latitude = location.latitude
        address.longitude = location.longitude
        address.save(update_fields=["latitude", "longitude"])
        return True
    return False

@login_required
def confirm_address_location(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)

    if request.method == "POST":
        latitude = request.POST.get("latitude")
        longitude = request.POST.get("longitude")

        if not latitude or not longitude:
            messages.error(request, "Invalid location selected.")
            return redirect("confirm_address_location", address_id=address.id)

        address.latitude = latitude
        address.longitude = longitude
        address.is_confirmed = True

        try:
            address.save(update_fields=["latitude", "longitude", "is_confirmed"])

            reverse_geocode_address(address)

            request.session["new_address_data"] = {
                "street": address.street,
                "city": address.city,
                "state": address.state,
                "pincode": address.pincode,
                "latitude": address.latitude,
                "longitude": address.longitude
            }

            messages.success(request, "Location confirmed. Please review your address.")
        except IntegrityError:
            messages.info(request, "An address with these details already exists.")
        return redirect("cart")
    
    if not address.latitude or not address.longitude:
        geolocator = Nominatim(user_agent="safecart")
        full_address = f"{address.street}, {address.city}, {address.state}, {address.pincode}"
        location = geolocator.geocode(full_address)
        if location:
            address.latitude = location.latitude
            address.longitude = location.longitude
            try:
                address.save(update_fields=["latitude", "longitude"])
            except IntegrityError:
                pass

    return render(request, "confirm_address_location.html", {
        "address": address
    })

@login_required
def use_current_location(request):
    latitude = request.GET.get("latitude")
    longitude = request.GET.get("longitude")

    if not latitude or not longitude:
        messages.error(request, "Unable to fetch location.")
        return redirect("cart")
    
    latitude = float(latitude)
    longitude = float(longitude)

    # reverse geocode
    geolocator = Nominatim(user_agent="safecart")
    location = geolocator.reverse(f"{latitude}, {longitude}", exactly_one=True)

    addr = location.raw.get("address", {}) if location else {}

    if not any([addr.get("road"), addr.get("city"), addr.get("town"), addr.get("postcode")]):
        messages.error(request, "Unable to detect address from location.")
        return redirect("cart")

    address,created = Address.objects.get_or_create(
        user=request.user,
        street=addr.get("road", "").strip(),
        city=(addr.get("city") or addr.get("town") or "").strip(),
        state=addr.get("state", "").strip(),
        pincode=addr.get("postcode", "").strip(),
        defaults={
            "latitude": latitude,
            "longitude": longitude,
            "is_confirmed": False
        }
    )

    if not created:
        address.latitude = latitude
        address.longitude = longitude
        address.is_confirmed = False
        address.save(update_fields=["latitude", "longitude", "is_confirmed"])

    return redirect('confirm_address_location', address.id)
    
def reverse_geocode_address(address):
    geolocator = Nominatim(user_agent="safecart")
    location = geolocator.reverse(
        (address.latitude, address.longitude),
        exactly_one=True
    )

    if not location:
        return

    addr = location.raw.get("address", {})

    address.street = (
        addr.get("road")
        or addr.get("neighbourhood")
        or addr.get("suburb", "")
    )
    address.city = (
        addr.get("city")
        or addr.get("town")
        or addr.get("village", "")
    )
    address.state = addr.get("state", "")
    address.pincode = addr.get("postcode", "")

    address.save(update_fields=[
        "street", "city", "state", "pincode"
    ])


@login_required
def save_address_and_map(request):
    street = request.GET.get("street")
    city = request.GET.get("city")
    state = request.GET.get("state")
    pincode = request.GET.get("pincode")

    if not all([street, city, state, pincode]):
        messages.error(request, "Invalid address data.")
        return redirect("cart")

    # Try to find a nearby address
    address, _ = Address.objects.get_or_create(
        user=request.user,
        street=street.strip(),
        city=city.strip(),
        state=state.strip(),
        pincode=pincode.strip(),
        defaults={"is_confirmed": False}
    )

    if not address:
        address = Address.objects.create(
            user=request.user,
            street=street,
            city=city,
            state=state,
            pincode=pincode,
            is_confirmed=False
        )

    geolocator = Nominatim(user_agent="safecart")
    fallback_addresses = [
        f"{street}, {city}, {state}, {pincode}",
        f"{city}, {state}, {pincode}",
        f"{state}, {pincode}",
        f"{pincode}"
    ]

    for addr_str in fallback_addresses:
        location = geolocator.geocode(addr_str)
        if location:
            address.latitude = location.latitude
            address.longitude = location.longitude
            address.save(update_fields=["latitude", "longitude"])
            break

    return redirect("confirm_address_location", address.id)

@login_required
def save_address_session(request):
    street = request.GET.get("street")
    city = request.GET.get("city")
    state = request.GET.get("state")
    pincode = request.GET.get("pincode")

    if not all([street, city, state, pincode]):
        return JsonResponse({"success": False})

    address = Address.objects.filter(
        user=request.user,
        street=street,
        city=city,
        state=state,
        pincode=pincode
    ).first()

    request.session["new_address_data"] = {
        "street": street,
        "city": city,
        "state": state,
        "pincode": pincode
    }
    return JsonResponse({
        "success": True,
        "is_confirmed": bool(address and address.is_confirmed)
    })

@login_required
def proceed_to_checkout(request):
    if request.method != "POST":
        return redirect("cart")

    cart_items = Cart.objects.filter(user=request.user).select_related('product')
    if not cart_items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect("cart")
    
    session_addr = request.session.get("new_address_data")
    if not session_addr:
        messages.info(request, "Please select and confirm an address before proceeding to checkout.")
        return redirect("cart")

    address = Address.objects.filter(
        user=request.user,
        street=session_addr["street"],
        city=session_addr["city"],
        state=session_addr["state"],
        pincode=session_addr["pincode"]
    ).first()

    if not address:
        messages.info(request, "Please confirm a valid address before proceeding to checkout.")
        return redirect("cart")
    
    if not address.is_confirmed:
        messages.info(request, "Please confirm your selected address on the map before proceeding to checkout.")
        return redirect("cart")

    if not all([address.street, address.city, address.state, address.pincode]):
        messages.info(request, "Please ensure your address has all required fields before checkout.")
        return redirect("cart")
    
    order = Order.objects.create(
        user=request.user,
        address=address,
        payment_type="COD",
        delivery_mode="secure",
        token_value=str(uuid.uuid4()),
        expires_at=None,
        status="Pending"
    )

    OrderItem.objects.bulk_create([
        OrderItem(
            order=order,
            product=item.product,
            quantity=item.quantity,
            price=item.product.price,
        )
        for item in cart_items
    ])
    
    cart_items.delete()

    request.session.pop("new_address_data", None)   

    messages.success(request, "Your order has been placed successfully!")
    return redirect("yourorders")

@login_required
def yourorders(request):
    context = build_customer_orders_context(request.user)
    return render(request, 'yourorders.html', context)


@login_required
@require_POST
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.status not in ['Pending', 'Packed']:
        messages.warning(request, "Only pending or packed orders can be cancelled.")
        return redirect('yourorders')

    order.status = 'Cancelled'
    order.save(update_fields=['status'])
    messages.success(request, f"Order #{order.id} has been cancelled.")
    return redirect('yourorders')

@login_required
@permission_required('store.can_view_seller_orders', raise_exception=True)
def sellerorders(request):
    context = build_seller_orders_context()
    return render(request, 'sellerorders.html', context)


@login_required
@permission_required('store.can_perform_admin_actions', raise_exception=True)
@require_POST
def toggle_delivery_mode(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.status in ["Shipped", "Delivered"]:
        messages.warning(request, "Delivery mode cannot be changed once the order is shipped or delivered.")
        return redirect("sellerorders")

    new_mode = "traditional" if order.delivery_mode == "secure" else "secure"
    update_fields = ["delivery_mode"]

    if new_mode == "traditional" and order.delivery_agent_id is None:
        agent = DeliveryAgent.objects.order_by("?").first()
        if agent:
            order.delivery_agent = agent
            update_fields.append("delivery_agent")
        else:
            messages.error(request, "No delivery agents available to assign for traditional delivery.")
            return redirect("sellerorders")
    elif new_mode == "secure":
        # Reset assignment/QR session so secure flow starts fresh.
        order.delivery_agent = None
        order.qr_scan_count = 0
        order.expires_at = None
        update_fields.extend(["delivery_agent", "qr_scan_count", "expires_at"])

    order.delivery_mode = new_mode
    order.save(update_fields=update_fields)
    log_security_event(
        order,
        "delivery_mode_switched",
        actor=request.user,
        outcome="success",
        details={"new_mode": new_mode},
    )
    messages.success(request, f"Order {order.id} updated to {order.get_delivery_mode_display()}.")
    return redirect("sellerorders")

@login_required
@permission_required('store.can_perform_admin_actions', raise_exception=True)
def make_delivery_agent(request, user_id):
    user = get_object_or_404(User, id=user_id)
    delivery_group, _ = Group.objects.get_or_create(name='DeliveryAgent')
    seller_group, _ = Group.objects.get_or_create(name='Seller')
    buyer_group, _ = Group.objects.get_or_create(name='Buyer')

    if delivery_group in user.groups.all():
        user.groups.remove(delivery_group)
        user.groups.remove(seller_group)
        user.groups.add(buyer_group)
        messages.success(request, f"{user.username} is now a Buyer.")
    else:
        user.groups.remove(buyer_group)
        user.groups.remove(seller_group)
        user.groups.add(delivery_group)
        messages.success(request, f"{user.username} is now a Delivery Agent.")

    return redirect('admin_dashboard')


@login_required
@permission_required('store.can_perform_admin_actions', raise_exception=True)
def make_seller(request, user_id):
    user = get_object_or_404(User, id=user_id)
    seller_group, _ = Group.objects.get_or_create(name='Seller')
    delivery_group, _ = Group.objects.get_or_create(name='DeliveryAgent')
    buyer_group, _ = Group.objects.get_or_create(name='Buyer')

    if seller_group in user.groups.all():
        user.groups.remove(seller_group)
        user.groups.remove(delivery_group)
        user.groups.add(buyer_group)
        messages.success(request, f"{user.username} is now a Buyer.")
    else:
        user.groups.remove(buyer_group)
        user.groups.remove(delivery_group)
        user.groups.add(seller_group)
        messages.success(request, f"{user.username} is now a Seller.")

    return redirect('admin_dashboard')


@login_required
@permission_required('store.can_perform_admin_actions', raise_exception=True)
def admin_dashboard(request):
    total_users = User.objects.filter(is_superuser=False).count()
    buyer_group, _ = Group.objects.get_or_create(name='Buyer')
    seller_group, _ = Group.objects.get_or_create(name='Seller')
    delivery_group, _ = Group.objects.get_or_create(name='DeliveryAgent')
    total_buyers = buyer_group.user_set.count()
    total_sellers = seller_group.user_set.count()
    total_delivery_agents = delivery_group.user_set.count()
    total_products = Product.objects.count()
    total_orders = Order.objects.count()

    users = User.objects.filter(is_superuser=False).order_by('id')
    users_info = [
        {
            'user': u,
            'is_delivery': delivery_group in u.groups.all(),
            'is_seller': seller_group in u.groups.all(),
            'role': (
                'Delivery Agent' if delivery_group in u.groups.all()
                else 'Seller' if seller_group in u.groups.all()
                else 'Buyer'
            ),
        }
        for u in users
    ]

    security_context = build_security_overview_context()
    comparison_context = build_delivery_comparison_context()

    context = {
        'total_users': total_users,
        'total_buyers': total_buyers,
        'total_sellers': total_sellers,
        'total_delivery_agents': total_delivery_agents,
        'total_products': total_products,
        'total_orders': total_orders,
        'users_info': users_info,
        **security_context,
        **comparison_context,
    }
    return render(request, 'dashboard/admin_dashboard.html', context)


@login_required
@permission_required('store.can_perform_admin_actions', raise_exception=True)
def admin_security_logs(request):
    context = build_security_logs_context(
        event_type=request.GET.get("event_type", "").strip(),
        outcome=request.GET.get("outcome", "").strip(),
        order_id=request.GET.get("order_id", "").strip(),
        delivery_mode=request.GET.get("delivery_mode", "").strip(),
    )
    return render(request, 'dashboard/admin_security_logs.html', context)


@login_required
@permission_required('store.can_deliver_order', raise_exception=True)
def delivery_dashboard(request):
    context = build_delivery_dashboard_context(request.user)
    return render(request, 'dashboard/delivery_dashboard.html', context)


@login_required
@permission_required('store.can_deliver_order', raise_exception=True)
def mark_order_delivered(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.delivery_mode != "traditional":
        messages.error(request, "Only traditional delivery orders can be marked delivered without OTP.")
        return redirect('delivery_dashboard')
    order.status = 'Delivered'
    order.expires_at = timezone.now()
    order.save(update_fields=['status', 'expires_at'])
    messages.success(request, f"Order {order.id} marked as delivered.")
    return redirect('delivery_dashboard')

def _render_delivery_order_page(request, order, *, route_only=False):
    security = get_order_security_snapshot(order)
    return render(request, 'dashboard/delivery_order_detail.html', {
        'order': order,
        'security': security,
        'route_only': route_only,
        'allow_handoff_actions': not route_only and order.delivery_mode != "traditional",
        'allow_request_new_otp': route_only and order.status not in ['Delivered', 'Cancelled'],
        'allow_mark_delivered': order.delivery_mode == "traditional" and order.status not in ['Delivered', 'Cancelled'],
        'page_heading': 'Route View' if route_only else 'Order Details',
        'status_note': (
            "QR expired. Route is still available and you can request a fresh OTP to complete delivery."
            if route_only else None
        ),
    })


def dashboard_redirect(request):
    user = request.user
    if user.is_superuser or user.groups.filter(name='Admin').exists():
        return redirect('admin_dashboard')
    elif user.groups.filter(name='Seller').exists():
        return redirect('sellerorders')
    elif user.groups.filter(name='DeliveryAgent').exists():
        return redirect('delivery_dashboard')
    else:
        return redirect('home')
    
@login_required
def manage_users(request):
    users = User.objects.filter(is_superuser=False)
    delivery_group, _ = Group.objects.get_or_create(name='DeliveryAgent')
    seller_group, _ = Group.objects.get_or_create(name='Seller')
    buyer_group, _ = Group.objects.get_or_create(name='Buyer')

    users_info = [
        {
            'user': u,
            'is_delivery': delivery_group in u.groups.all(),
            'is_seller': seller_group in u.groups.all(),
            'role': (
                'Delivery Agent' if delivery_group in u.groups.all()
                else 'Seller' if seller_group in u.groups.all()
                else 'Buyer'
            ),
        }
        for u in users
    ]

    context = {
        'users_info': users_info,
        'total_users': users.count(),
        'total_buyers': buyer_group.user_set.count(),
        'total_sellers': seller_group.user_set.count(),
        'total_delivery_agents': delivery_group.user_set.count(),
        'total_products': Product.objects.count(),
        'total_orders': Order.objects.count(),
    }
    return render(request, 'dashboard/admin_dashboard.html', context)

@login_required
@permission_required('store.can_deliver_order', raise_exception=True)
def delivery_order_detail(request):
    order_id = request.GET.get('order-id')
    order = get_object_or_404(Order, id=order_id)
    try:
        validate_delivery_agent_order_access(order, request.user)
    except DeliveryAccessError as exc:
        getattr(messages, exc.level)(request, str(exc))
        return redirect('delivery_dashboard')
    if order.delivery_mode != "traditional" and order.delivery_qr_is_expired():
        messages.warning(request, "This QR code has expired. Route view is still available.")
        return redirect(f"{reverse('delivery_route_detail')}?order-id={order.id}")

    return _render_delivery_order_page(request, order, route_only=False)


@login_required
@permission_required('store.can_deliver_order', raise_exception=True)
def delivery_route_detail(request):
    order_id = request.GET.get('order-id')
    order = get_object_or_404(Order, id=order_id)
    try:
        validate_delivery_agent_order_access(order, request.user)
    except DeliveryAccessError as exc:
        getattr(messages, exc.level)(request, str(exc))
        return redirect('delivery_dashboard')
    if order.delivery_mode == "traditional":
        messages.info(request, "Traditional delivery uses the full order view.")
        return redirect(f"{reverse('delivery_order_detail')}?order-id={order.id}")
    if not order.delivery_qr_is_expired():
        messages.info(request, "This order still has an active QR window. Opening the full order view.")
        return redirect(f"{reverse('delivery_order_detail')}?order-id={order.id}")

    return _render_delivery_order_page(request, order, route_only=True)

@login_required
@permission_required('store.can_deliver_order', raise_exception=True)
@require_GET
def get_order_by_token(request):
    token = (request.GET.get('token') or '').strip()
    try:
        order = claim_order_from_token(token=token, user=request.user)
        return JsonResponse({
            'success': True,
            'order_id': order.id,
            'security': get_order_security_snapshot(order),
        })
    except DeliveryQRScanError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=exc.status_code)
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Order not found'})

@login_required

def generate_order_otp(request, order_id):

    order = get_object_or_404(Order, id=order_id)
    try:
        payload = get_or_create_order_otp_payload(order, request.user)
    except (OTPAccessError, OTPValidationError) as exc:
        return JsonResponse({
            "success": False,
            "error": str(exc)
        }, status=exc.status_code)

    return JsonResponse({
        "success": True,
        "security": get_order_security_snapshot(order),
        **payload,
    })

@login_required
@require_POST
def verify_otp(request, order_id):

    order = get_object_or_404(Order, id=order_id)

    data = json.loads(request.body)
    try:
        result = verify_order_otp_service(
            order,
            request.user,
            customer_half=data.get("customer_half"),
            agent_half=data.get("agent_half"),
        )
    except OTPValidationError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=exc.status_code)

    return JsonResponse({
        **result,
        "security": get_order_security_snapshot(order),
    })

@login_required
def get_order_otp_halves(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    try:
        payload = get_order_otp_payload(order, request.user)
    except (OTPAccessError, OTPValidationError) as exc:
        return JsonResponse({
            "success": False,
            "error": str(exc)
        }, status=exc.status_code)

    return JsonResponse({
        "success": True,
        "security": get_order_security_snapshot(order),
        **payload,
    })

# Render customer tracking map
@login_required
def customer_track_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'customer_track_order.html', {'order': order})

# API: Return delivery agent's current coordinates
@login_required
def get_agent_location(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if order.status in ['Delivered', 'Cancelled']:
        return JsonResponse({
            'latitude': 0,
            'longitude': 0,
            'status': order.status,
            'trackable': False,
            'message': 'Order is no longer trackable.'
        })

    agent = order.delivery_agent
    if agent and agent.latitude is not None and agent.longitude is not None:
        return JsonResponse({
            'latitude': agent.latitude,
            'longitude': agent.longitude,
            'status': order.status,
            'trackable': True
        })
    return JsonResponse({
        'latitude': 0,
        'longitude': 0,
        'status': order.status,
        'trackable': True,
        'message': 'Waiting for delivery agent location.'
    })

import json

@login_required
@permission_required('store.can_deliver_order', raise_exception=True)
@require_POST
def update_agent_location(request, order_id):
    """
    Endpoint for delivery agent to send their latest latitude/longitude
    Expects POST: { "latitude": 28.6139, "longitude": 77.2090 }
    """
    try:
        data = json.loads(request.body)
        lat = data.get("latitude")
        lng = data.get("longitude")
    except (TypeError, json.JSONDecodeError):
        return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)

    if lat is None or lng is None:
        return JsonResponse({"status": "error", "message": "Latitude and longitude are required"}, status=400)

    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return JsonResponse({"status": "error", "message": "Latitude/longitude must be numeric"}, status=400)

    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return JsonResponse({"status": "error", "message": "Latitude/longitude out of range"}, status=400)

    order = get_object_or_404(Order, id=order_id)
    agent = DeliveryAgent.objects.filter(user=request.user).first()
    if not agent:
        return JsonResponse({"status": "error", "message": "Delivery agent profile not found"}, status=404)

    if order.delivery_agent_id is None:
        order.delivery_agent = agent
        order.save(update_fields=["delivery_agent"])
    elif order.delivery_agent_id != agent.id:
        return JsonResponse({"status": "error", "message": "Order is assigned to another delivery agent"}, status=403)

    agent.latitude = lat
    agent.longitude = lng
    agent.save(update_fields=["latitude", "longitude"])

    if order.status in ["Pending", "Packed"]:
        order.status = "Shipped"
        order.save(update_fields=["status"])

    return JsonResponse({"status": "success", "latitude": lat, "longitude": lng})

@login_required
def join_order_call(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    allowed, role, error_message = _can_access_order_call(order, request.user)
    if not allowed:
        messages.error(request, error_message)
        if role == "agent":
            return redirect(f"{reverse('delivery_order_detail')}?order-id={order.id}")
        return redirect("yourorders")

    return render(request, "order_call_room.html", {
        "order": order,
        "role": role,
        "hide_navbar": role == "agent",
    })


def _can_access_order_call(order, user):
    if order.status in ["Delivered", "Cancelled"]:
        return False, None, "Call is unavailable for delivered or cancelled orders."

    if order.delivery_agent_id is None:
        return False, None, "Delivery agent is not assigned yet."

    if order.user_id == user.id and order.delivery_agent and order.delivery_agent.user_id == user.id:
        return False, None, "This account is both customer and delivery agent. Use two different accounts."

    if order.user_id == user.id:
        if order.status not in ["Packed", "Shipped"]:
            return False, "customer", "Call is available only when order is packed or shipped."
        return True, "customer", None

    if order.delivery_agent and order.delivery_agent.user_id == user.id:
        if order.status not in ["Packed", "Shipped"]:
            return False, "agent", "Call is available only for packed or shipped orders."
        return True, "agent", None

    return False, None, "You are not allowed to join this order call."


def _mark_session_closed(session, status_value):
    session.is_active = False
    session.status = status_value
    session.ended_at = timezone.now()
    session.save(update_fields=["is_active", "status", "ended_at", "updated_at"])


@login_required
@require_POST
def start_order_call(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    allowed, role, error_message = _can_access_order_call(order, request.user)
    if not allowed:
        logger.warning("start_order_call denied order=%s user=%s role=%s error=%s", order.id, request.user.id, role, error_message)
        return JsonResponse({"status": "error", "message": error_message}, status=403)

    session, created = OrderCallSession.objects.get_or_create(
        order=order,
        defaults={
            "started_by": request.user,
            "is_active": True,
            "status": "ringing",
            "ended_at": None,
            "accepted_at": None,
        }
    )
    if not created:
        if session.is_active and session.status == "ringing":
            if session.started_by_id != request.user.id:
                session.status = "ongoing"
                session.accepted_at = timezone.now()
                session.save(update_fields=["status", "accepted_at", "updated_at"])
        elif not session.is_active or session.status in ["ended", "rejected", "missed"]:
            session.is_active = True
            session.status = "ringing"
            session.started_by = request.user
            session.accepted_at = None
            session.ended_at = None
            session.save(update_fields=[
                "is_active",
                "status",
                "started_by",
                "accepted_at",
                "ended_at",
                "updated_at",
            ])
            session.signals.all().delete()

    logger.info(
        "start_order_call ok order=%s user=%s role=%s session=%s created=%s status=%s active=%s",
        order.id, request.user.id, role, session.id, created, session.status, session.is_active
    )

    return JsonResponse({
        "status": "success",
        "session_id": session.id,
        "role": role,
        "order_status": order.status,
        "call_status": session.status,
        "is_caller": session.started_by_id == request.user.id,
    })


@login_required
@require_POST
def send_order_call_signal(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    allowed, _, error_message = _can_access_order_call(order, request.user)
    if not allowed:
        return JsonResponse({"status": "error", "message": error_message}, status=403)

    session = getattr(order, "call_session", None)
    if not session or not session.is_active:
        return JsonResponse({"status": "error", "message": "No active call session."}, status=400)

    try:
        payload = json.loads(request.body)
    except (TypeError, json.JSONDecodeError):
        return JsonResponse({"status": "error", "message": "Invalid JSON body."}, status=400)

    signal_type = payload.get("type")
    signal_payload = payload.get("payload", {})

    if signal_type not in {"offer", "answer", "ice", "bye"}:
        return JsonResponse({"status": "error", "message": "Invalid signal type."}, status=400)
    if not isinstance(signal_payload, dict):
        return JsonResponse({"status": "error", "message": "Signal payload must be an object."}, status=400)

    signal = OrderCallSignal.objects.create(
        session=session,
        sender=request.user,
        signal_type=signal_type,
        payload=signal_payload,
    )

    if signal_type == "bye":
        _mark_session_closed(session, "ended")

    return JsonResponse({"status": "success", "signal_id": signal.id})


@login_required
def poll_order_call_signals(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    allowed, _, error_message = _can_access_order_call(order, request.user)
    if not allowed:
        return JsonResponse({"status": "error", "message": error_message}, status=403)

    session = getattr(order, "call_session", None)
    if not session:
        return JsonResponse({
            "status": "success",
            "session_active": False,
            "signals": [],
            "last_id": 0,
        })

    try:
        after_id = int(request.GET.get("after_id", "0"))
    except ValueError:
        after_id = 0

    signals = (
        session.signals
        .filter(id__gt=after_id)
        .exclude(sender=request.user)
        .order_by("id")
    )

    serialized_signals = [
        {
            "id": s.id,
            "type": s.signal_type,
            "payload": s.payload,
            "created_at": s.created_at.isoformat(),
        }
        for s in signals
    ]
    last_id = serialized_signals[-1]["id"] if serialized_signals else after_id

    return JsonResponse({
        "status": "success",
        "session_active": session.is_active,
        "call_status": session.status,
        "started_by_user_id": session.started_by_id,
        "signals": serialized_signals,
        "last_id": last_id,
    })


@login_required
def get_incoming_order_calls(request):
    logger.info("get_incoming_order_calls user=%s", request.user.id)
    incoming_sessions = (
        OrderCallSession.objects
        .filter(is_active=True, status="ringing")
        .exclude(started_by=request.user)
        .filter(
            Q(order__user=request.user)
            | Q(order__delivery_agent__user=request.user)
        )
        .select_related("order", "started_by")
        .order_by("-updated_at")
    )

    calls = [
        {
            "order_id": session.order_id,
            "from_name": (
                session.started_by.get_full_name().strip()
                if session.started_by else "Unknown"
            ) or (session.started_by.username if session.started_by else "Unknown"),
            "role": "customer" if session.order.user_id == request.user.id else "agent",
            "started_at": session.started_at.isoformat(),
        }
        for session in incoming_sessions
    ]
    logger.info("get_incoming_order_calls result user=%s count=%s orders=%s",
                request.user.id, len(calls), [c["order_id"] for c in calls])
    return JsonResponse({"status": "success", "calls": calls})


@login_required
@require_POST
def accept_order_call(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    allowed, _, error_message = _can_access_order_call(order, request.user)
    if not allowed:
        return JsonResponse({"status": "error", "message": error_message}, status=403)

    session = getattr(order, "call_session", None)
    if not session or not session.is_active:
        return JsonResponse({"status": "error", "message": "No active incoming call."}, status=400)
    if session.started_by_id == request.user.id:
        return JsonResponse({"status": "error", "message": "Caller cannot accept own call."}, status=400)

    session.status = "ongoing"
    session.accepted_at = timezone.now()
    session.save(update_fields=["status", "accepted_at", "updated_at"])
    return JsonResponse({"status": "success", "message": "Call accepted."})


@login_required
@require_POST
def reject_order_call(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    allowed, _, error_message = _can_access_order_call(order, request.user)
    if not allowed:
        return JsonResponse({"status": "error", "message": error_message}, status=403)

    session = getattr(order, "call_session", None)
    if not session or not session.is_active:
        return JsonResponse({"status": "success", "message": "No active incoming call."})
    if session.started_by_id == request.user.id:
        return JsonResponse({"status": "error", "message": "Caller cannot reject own call."}, status=400)

    OrderCallSignal.objects.create(
        session=session,
        sender=request.user,
        signal_type="bye",
        payload={"reason": "rejected"},
    )
    _mark_session_closed(session, "rejected")
    return JsonResponse({"status": "success", "message": "Call rejected."})


@login_required
@require_POST
def end_order_call(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    allowed, _, error_message = _can_access_order_call(order, request.user)
    if not allowed:
        return JsonResponse({"status": "error", "message": error_message}, status=403)

    session = getattr(order, "call_session", None)
    if not session or not session.is_active:
        return JsonResponse({"status": "success", "message": "No active session to end."})

    OrderCallSignal.objects.create(
        session=session,
        sender=request.user,
        signal_type="bye",
        payload={"reason": "ended"},
    )
    _mark_session_closed(session, "ended")

    return JsonResponse({"status": "success", "message": "Call ended."})

@login_required
@require_GET
def debug_order_call_state(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    session = OrderCallSession.objects.filter(order=order).first()

    payload = {
        "order_id": order.id,
        "order_status": order.status,
        "order_user_id": order.user_id,
        "delivery_agent_id": order.delivery_agent_id,
        "delivery_agent_user_id": order.delivery_agent.user_id if order.delivery_agent else None,
        "current_user_id": request.user.id,
        "allowed": None,
        "role": None,
        "error": None,
        "session": None,
        "recent_signals": [],
    }

    allowed, role, error_message = _can_access_order_call(order, request.user)
    payload.update({"allowed": allowed, "role": role, "error": error_message})

    if session:
        payload["session"] = {
            "id": session.id,
            "is_active": session.is_active,
            "status": session.status,
            "started_by_id": session.started_by_id,
            "started_at": session.started_at.isoformat(),
            "accepted_at": session.accepted_at.isoformat() if session.accepted_at else None,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "updated_at": session.updated_at.isoformat(),
        }
        payload["recent_signals"] = [
            {
                "id": s.id,
                "type": s.signal_type,
                "sender_id": s.sender_id,
                "created_at": s.created_at.isoformat(),
            }
            for s in session.signals.order_by("-id")[:10]
        ]

    return JsonResponse(payload)

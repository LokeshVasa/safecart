from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import Group, User
from django.core.mail import EmailMessage
from django.urls import reverse
from django.utils import timezone

from store.models import PasswordReset


class AuthServiceError(Exception):
    pass


def register_buyer_user(form):
    user = form.save()
    buyer_group, _ = Group.objects.get_or_create(name="Buyer")
    user.groups.add(buyer_group)
    return user


def authenticate_user_by_identifier(request, identifier, password):
    user = None
    if User.objects.filter(email=identifier).exists():
        try:
            user_obj = User.objects.get(email=identifier)
            user = authenticate(request, username=user_obj.username, password=password)
        except User.DoesNotExist:
            user = None
    else:
        user = authenticate(request, username=identifier, password=password)
    return user


def get_post_login_redirect_name(user):
    if user.is_superuser or user.groups.filter(name="Admin").exists():
        return "admin_dashboard"
    if user.groups.filter(name="Seller").exists():
        return "sellerorders"
    if user.groups.filter(name="DeliveryAgent").exists():
        return "delivery_dashboard"
    return "home"


def create_password_reset_request(*, email, scheme, host):
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist as exc:
        raise AuthServiceError(f"No user with email '{email}' found") from exc

    password_reset = PasswordReset.objects.create(user=user)
    password_reset_url = reverse("reset-password", kwargs={"reset_id": password_reset.reset_id})
    full_password_reset_url = f"{scheme}://{host}{password_reset_url}"

    email_body = f"Reset your password using the link below:\n\n\n{full_password_reset_url}"
    email_message = EmailMessage(
        "Reset your password",
        email_body,
        settings.EMAIL_HOST_USER,
        [email],
    )
    email_message.fail_silently = True
    email_message.send()
    return password_reset


def password_reset_exists(reset_id):
    return PasswordReset.objects.filter(reset_id=reset_id).exists()


def reset_password_with_token(*, reset_id, password, confirm_password):
    try:
        password_reset = PasswordReset.objects.get(reset_id=reset_id)
    except PasswordReset.DoesNotExist as exc:
        raise AuthServiceError("Invalid reset id") from exc

    errors = []
    if password != confirm_password:
        errors.append("Passwords do not match")

    if len(password) < 5:
        errors.append("Password must be at least 5 characters long")

    expiration_time = password_reset.created_when + timezone.timedelta(minutes=10)
    if timezone.now() > expiration_time:
        errors.append("Reset link has expired")
        password_reset.delete()

    if errors:
        return {"success": False, "errors": errors}

    user = password_reset.user
    user.set_password(password)
    user.save()
    password_reset.delete()
    return {"success": True}

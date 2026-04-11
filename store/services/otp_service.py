import hashlib
import random
from datetime import timedelta

from django.utils import timezone

from store.models import DeliveryAgent, OrderOTP
from store.services.security_service import (
    DeliverySecurityError,
    get_order_security_snapshot,
    log_security_event,
    validate_otp_read_security,
    validate_otp_request_security,
)
from store.utils import decrypt_value, encrypt_value


class OTPValidationError(Exception):
    status_code = 400


class OTPAccessError(OTPValidationError):
    status_code = 403


MAX_OTP_ATTEMPTS = 5
OTP_EXPIRY_MINUTES = 10


def _ensure_otp_access(order, user):
    if user.groups.filter(name="DeliveryAgent").exists():
        delivery_agent = DeliveryAgent.objects.filter(user=user).first()
        if not delivery_agent or order.delivery_agent_id != delivery_agent.id:
            raise OTPAccessError("You can only request OTP for your assigned order.")
        return "agent"

    if order.user_id != user.id:
        raise OTPAccessError("You are not allowed to request OTP for this order.")
    return "customer"


def get_or_create_order_otp_payload(order, user):
    _ensure_otp_access(order, user)

    try:
        validate_otp_request_security(order)
    except DeliverySecurityError as exc:
        log_security_event(
            order,
            "otp_request_blocked",
            actor=user,
            outcome="blocked",
            details={"reason": str(exc)},
        )
        raise OTPValidationError(str(exc)) from exc

    otp_obj = OrderOTP.objects.filter(order=order).first()
    if otp_obj and otp_obj.is_active and not otp_obj.is_expired():
        log_security_event(
            order,
            "otp_requested",
            actor=user,
            outcome="success",
            details={"security_stage": get_order_security_snapshot(order)["security_stage"], "reused": True},
        )
        return {
            "agent_half": decrypt_value(otp_obj.enc_agent_half),
            "customer_half": decrypt_value(otp_obj.enc_customer_half),
            "customer_verified": otp_obj.customer_verified,
            "agent_verified": otp_obj.agent_verified,
        }

    otp = str(random.randint(10000000, 99999999))
    customer_half = otp[:4]
    agent_half = otp[4:]

    OrderOTP.objects.update_or_create(
        order=order,
        defaults={
            "otp_hash": hashlib.sha256(otp.encode()).hexdigest(),
            "enc_customer_half": encrypt_value(customer_half),
            "enc_agent_half": encrypt_value(agent_half),
            "expires_at": timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES),
            "is_active": True,
            "attempts": 0,
            "customer_verified": False,
            "agent_verified": False,
        },
    )

    log_security_event(
        order,
        "otp_requested",
        actor=user,
        outcome="success",
        details={"security_stage": get_order_security_snapshot(order)["security_stage"], "reused": False},
    )

    return {
        "agent_half": agent_half,
        "customer_half": customer_half,
        "customer_verified": False,
        "agent_verified": False,
    }


def verify_order_otp(order, user, *, customer_half, agent_half):
    try:
        otp_obj = order.otp
    except OrderOTP.DoesNotExist as exc:
        log_security_event(order, "otp_verify_failed", actor=user, outcome="failed", details={"reason": "otp_not_found"})
        raise OTPValidationError("OTP not found") from exc

    if otp_obj.is_expired():
        otp_obj.is_active = False
        otp_obj.save(update_fields=["is_active"])
        log_security_event(order, "otp_verify_failed", actor=user, outcome="failed", details={"reason": "otp_expired"})
        raise OTPValidationError("OTP expired")

    if otp_obj.attempts >= MAX_OTP_ATTEMPTS:
        otp_obj.is_active = False
        otp_obj.save(update_fields=["is_active"])
        log_security_event(order, "otp_verify_failed", actor=user, outcome="blocked", details={"reason": "max_attempts"})
        raise OTPValidationError("Maximum attempts exceeded. Generate a new OTP.")

    if not customer_half or not agent_half:
        log_security_event(order, "otp_verify_failed", actor=user, outcome="failed", details={"reason": "invalid_format"})
        raise OTPValidationError("Invalid OTP format")

    full_otp = customer_half + agent_half
    hashed = hashlib.sha256(full_otp.encode()).hexdigest()

    if hashed != otp_obj.otp_hash:
        otp_obj.attempts += 1
        otp_obj.save(update_fields=["attempts"])
        remaining = MAX_OTP_ATTEMPTS - otp_obj.attempts
        log_security_event(
            order,
            "otp_verify_failed",
            actor=user,
            outcome="failed",
            details={"reason": "hash_mismatch", "remaining_attempts": remaining},
        )
        return {
            "success": False,
            "remaining_attempts": remaining,
        }

    if user.groups.filter(name="DeliveryAgent").exists():
        otp_obj.agent_verified = True
    else:
        otp_obj.customer_verified = True

    otp_obj.save(update_fields=["agent_verified", "customer_verified"])
    log_security_event(
        order,
        "otp_verify_success",
        actor=user,
        outcome="success",
        details={
            "customer_verified": otp_obj.customer_verified,
            "agent_verified": otp_obj.agent_verified,
            "security_stage": get_order_security_snapshot(order)["security_stage"],
        },
    )

    order_delivered = False
    if otp_obj.agent_verified and otp_obj.customer_verified:
        otp_obj.is_active = False
        otp_obj.save(update_fields=["is_active"])

        order.status = "Delivered"
        order.expires_at = timezone.now()
        order.save(update_fields=["status", "expires_at"])
        order_delivered = True
        log_security_event(
            order,
            "order_delivered",
            actor=user,
            outcome="success",
            details={"security_stage": get_order_security_snapshot(order)["security_stage"]},
        )

    return {
        "success": True,
        "order_status": order.status,
        "order_delivered": order_delivered,
    }


def get_order_otp_payload(order, user):
    is_customer = order.user_id == user.id
    is_assigned_agent = (
        order.delivery_agent is not None
        and order.delivery_agent.user_id == user.id
    )
    if not (is_customer or is_assigned_agent):
        raise OTPAccessError("You are not allowed to access this order OTP.")

    try:
        validate_otp_read_security(order)
    except DeliverySecurityError as exc:
        log_security_event(
            order,
            "otp_request_blocked",
            actor=user,
            outcome="blocked",
            details={"reason": str(exc), "read": True},
        )
        raise OTPValidationError(str(exc)) from exc

    otp_obj = OrderOTP.objects.filter(order=order).first()
    if not otp_obj:
        raise OTPValidationError("OTP not generated")

    return {
        "customer_half": decrypt_value(otp_obj.enc_customer_half),
        "agent_half": decrypt_value(otp_obj.enc_agent_half),
        "customer_verified": otp_obj.customer_verified,
        "agent_verified": otp_obj.agent_verified,
        "order_status": order.status,
        "order_delivered": order.status == "Delivered",
    }

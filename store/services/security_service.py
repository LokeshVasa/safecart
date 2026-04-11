from django.shortcuts import get_object_or_404
from django.utils import timezone

from store.models import DeliveryAgent, Order, OrderOTP


class DeliveryAccessError(Exception):
    def __init__(self, message, level="error"):
        super().__init__(message)
        self.level = level


class DeliverySecurityError(Exception):
    pass


DELIVERY_STATUS_PRIORITY = {
    "Pending": 0,
    "Packed": 1,
    "Shipped": 2,
    "Delivered": 3,
    "Cancelled": 4,
}


def get_order_security_snapshot(order):
    otp_obj = OrderOTP.objects.filter(order=order).first()
    is_closed = order.status in ["Delivered", "Cancelled"]
    qr_expired = order.delivery_qr_is_expired()
    has_remaining_scans = order.delivery_qr_has_remaining_scans()
    qr_window_started = order.qr_scan_count > 0 and order.expires_at is not None
    qr_window_active = qr_window_started and not qr_expired
    otp_exists = otp_obj is not None
    otp_active = bool(otp_obj and otp_obj.is_active)
    otp_expired = bool(otp_obj and otp_obj.is_expired())
    customer_verified = bool(otp_obj and otp_obj.customer_verified)
    agent_verified = bool(otp_obj and otp_obj.agent_verified)
    both_verified = customer_verified and agent_verified
    full_delivery_access = not is_closed and not qr_expired
    route_only_access = not is_closed and qr_expired
    otp_reissue_allowed = not is_closed and (full_delivery_access or route_only_access)

    if order.status == "Delivered":
        security_stage = "delivered"
    elif order.status == "Cancelled":
        security_stage = "cancelled"
    elif both_verified:
        security_stage = "verified"
    elif otp_active:
        security_stage = "otp_active"
    elif route_only_access:
        security_stage = "route_only"
    elif full_delivery_access:
        security_stage = "qr_active"
    else:
        security_stage = "pending"

    return {
        "security_stage": security_stage,
        "is_closed": is_closed,
        "qr_scan_count": order.qr_scan_count,
        "qr_scan_limit": Order.DELIVERY_QR_MAX_SCANS,
        "has_remaining_scans": has_remaining_scans,
        "remaining_scans": max(0, Order.DELIVERY_QR_MAX_SCANS - order.qr_scan_count),
        "qr_window_started": qr_window_started,
        "qr_window_active": qr_window_active,
        "qr_expired": qr_expired,
        "full_delivery_access": full_delivery_access,
        "route_only_access": route_only_access,
        "otp_exists": otp_exists,
        "otp_active": otp_active,
        "otp_expired": otp_expired,
        "customer_verified": customer_verified,
        "agent_verified": agent_verified,
        "both_verified": both_verified,
        "otp_reissue_allowed": otp_reissue_allowed,
    }


def validate_qr_scan_security(order):
    security = get_order_security_snapshot(order)
    if order.status == "Delivered":
        raise DeliverySecurityError("QR scanning is unavailable for delivered orders.")
    if order.status == "Cancelled":
        raise DeliverySecurityError("QR scanning is unavailable for cancelled orders.")
    if not security["has_remaining_scans"]:
        raise DeliverySecurityError(
            f"This QR code can only be scanned {security['qr_scan_limit']} times."
        )
    return security


def validate_otp_request_security(order):
    security = get_order_security_snapshot(order)
    if order.status == "Delivered":
        raise DeliverySecurityError("Order already delivered")
    if order.status == "Cancelled":
        raise DeliverySecurityError("Safe Handshake is unavailable for cancelled orders.")
    if not security["otp_reissue_allowed"]:
        raise DeliverySecurityError("OTP request is blocked for this order.")
    return security


def validate_otp_read_security(order):
    security = get_order_security_snapshot(order)
    if order.status == "Cancelled":
        raise DeliverySecurityError("Safe Handshake is unavailable for cancelled orders.")
    return security


def get_delivery_agent_for_user(user):
    return get_object_or_404(DeliveryAgent, user=user)


def validate_delivery_agent_order_access(order, user):
    delivery_agent = get_delivery_agent_for_user(user)
    if order.delivery_agent_id != delivery_agent.id:
        raise DeliveryAccessError("This order is assigned to another delivery agent.")
    if order.status in ["Delivered", "Cancelled"]:
        raise DeliveryAccessError(
            f"This order is already {order.status.lower()}.",
            level="warning",
        )
    return delivery_agent


def build_delivery_dashboard_context(user):
    assigned_orders_qs = (
        Order.objects.filter(delivery_agent__user=user)
        .select_related("user", "address")
        .order_by("-created_at")
    )

    assigned_orders = []
    current_time = timezone.now()
    for order in assigned_orders_qs:
        security = get_order_security_snapshot(order)
        remaining_seconds = None
        if order.expires_at and order.qr_scan_count > 0:
            remaining_seconds = max(
                0,
                int((order.expires_at - current_time).total_seconds())
            )

        assigned_orders.append({
            "id": order.id,
            "customer_name": order.user.username,
            "status": order.status,
            "pincode": order.address.pincode,
            "created_at": order.created_at,
            "qr_scan_count": security["qr_scan_count"],
            "remaining_scans": security["remaining_scans"],
            "expires_at": order.expires_at,
            "remaining_seconds": remaining_seconds,
            "is_expired": security["qr_expired"],
            "can_open_order": security["full_delivery_access"],
            "can_view_route": security["route_only_access"],
            "security": security,
        })

    assigned_orders.sort(
        key=lambda order: (
            DELIVERY_STATUS_PRIORITY.get(order["status"], 99),
            -order["created_at"].timestamp()
        )
    )

    stats = {
        "assigned_count": len(assigned_orders),
        "active_count": sum(1 for order in assigned_orders if order["status"] not in ["Delivered", "Cancelled"]),
        "delivered_count": sum(1 for order in assigned_orders if order["status"] == "Delivered"),
        "available_count": Order.objects.filter(delivery_agent__isnull=True).exclude(
            status__in=["Delivered", "Cancelled"]
        ).count(),
        "qr_expiry_hours": Order.DELIVERY_QR_EXPIRY_HOURS,
        "qr_max_scans": Order.DELIVERY_QR_MAX_SCANS,
    }

    return {
        "assigned_orders": assigned_orders,
        "stats": stats,
    }

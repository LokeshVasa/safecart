from django.shortcuts import get_object_or_404
from django.utils import timezone

from store.models import DeliveryAgent, Order


class DeliveryAccessError(Exception):
    def __init__(self, message, level="error"):
        super().__init__(message)
        self.level = level


DELIVERY_STATUS_PRIORITY = {
    "Pending": 0,
    "Packed": 1,
    "Shipped": 2,
    "Delivered": 3,
    "Cancelled": 4,
}


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
        remaining_seconds = None
        if order.expires_at and order.qr_scan_count > 0:
            remaining_seconds = max(
                0,
                int((order.expires_at - current_time).total_seconds())
            )

        is_expired = order.delivery_qr_is_expired()
        is_closed = order.status in ["Delivered", "Cancelled"]
        assigned_orders.append({
            "id": order.id,
            "customer_name": order.user.username,
            "status": order.status,
            "pincode": order.address.pincode,
            "created_at": order.created_at,
            "qr_scan_count": order.qr_scan_count,
            "remaining_scans": max(0, Order.DELIVERY_QR_MAX_SCANS - order.qr_scan_count),
            "expires_at": order.expires_at,
            "remaining_seconds": remaining_seconds,
            "is_expired": is_expired,
            "can_open_order": not is_closed and not is_expired,
            "can_view_route": not is_closed and is_expired,
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

import logging
from collections import OrderedDict

from django.db import models
from django.db.utils import OperationalError, ProgrammingError
from django.shortcuts import get_object_or_404
from django.utils import timezone

from store.models import DeliveryAgent, Order, OrderOTP, SecurityEventLog


logger = logging.getLogger(__name__)


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

    security_stage_labels = {
        "delivered": "Delivered",
        "cancelled": "Cancelled",
        "verified": "Verified",
        "otp_active": "OTP Active",
        "route_only": "Route Only",
        "qr_active": "QR Active",
        "pending": "Pending",
    }
    security_badge_variants = {
        "delivered": "success",
        "cancelled": "danger",
        "verified": "success",
        "otp_active": "info",
        "route_only": "warning",
        "qr_active": "primary",
        "pending": "secondary",
    }
    show_security_badge = security_stage in {"verified", "otp_active", "route_only", "qr_active"}

    return {
        "security_stage": security_stage,
        "security_stage_label": security_stage_labels.get(security_stage, security_stage.replace("_", " ").title()),
        "security_badge_variant": security_badge_variants.get(security_stage, "secondary"),
        "show_security_badge": show_security_badge,
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
    if order.delivery_mode == "traditional":
        raise DeliverySecurityError("Traditional delivery does not require OTP verification.")
    if order.status == "Delivered":
        raise DeliverySecurityError("Order already delivered")
    if order.status == "Cancelled":
        raise DeliverySecurityError("Safe Handshake is unavailable for cancelled orders.")
    if not security["otp_reissue_allowed"]:
        raise DeliverySecurityError("OTP request is blocked for this order.")
    return security


def validate_otp_read_security(order):
    security = get_order_security_snapshot(order)
    if order.delivery_mode == "traditional":
        raise DeliverySecurityError("Traditional delivery does not require OTP verification.")
    if order.status == "Cancelled":
        raise DeliverySecurityError("Safe Handshake is unavailable for cancelled orders.")
    return security


def log_security_event(order, event_type, *, actor=None, outcome="success", details=None):
    try:
        return SecurityEventLog.objects.create(
            order=order,
            actor=actor,
            event_type=event_type,
            outcome=outcome,
            duration_ms=details.pop("duration_ms", None) if isinstance(details, dict) and "duration_ms" in details else None,
            details=details or {},
        )
    except (OperationalError, ProgrammingError):
        logger.warning(
            "Security event logging skipped because the table is unavailable.",
            exc_info=True,
        )
        return None


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
            "delivery_mode": order.delivery_mode,
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


def build_security_overview_context(*, recent_limit=8):
    recent_events_qs = (
        SecurityEventLog.objects
        .select_related("order", "actor")
        .order_by("-created_at")[:recent_limit]
    )

    recent_events = [
        {
            "event_type": event.event_type,
            "event_label": event.get_event_type_display(),
            "outcome": event.outcome,
            "order_id": event.order_id,
            "actor_name": event.actor.username if event.actor else "System",
            "created_at": event.created_at,
            "details": event.details or {},
        }
        for event in recent_events_qs
    ]

    return {
        "security_stats": {
            "total_events": SecurityEventLog.objects.count(),
            "blocked_events": SecurityEventLog.objects.filter(outcome="blocked").count(),
            "failed_events": SecurityEventLog.objects.filter(outcome="failed").count(),
            "successful_deliveries": SecurityEventLog.objects.filter(event_type="order_delivered").count(),
            "avg_qr_scan_ms": (
                round(
                    SecurityEventLog.objects.filter(event_type="qr_scan", duration_ms__isnull=False)
                    .aggregate(avg=models.Avg("duration_ms"))["avg"] or 0
                )
            ),
            "avg_otp_request_ms": (
                round(
                    SecurityEventLog.objects.filter(event_type="otp_requested", duration_ms__isnull=False)
                    .aggregate(avg=models.Avg("duration_ms"))["avg"] or 0
                )
            ),
            "avg_otp_verify_ms": (
                round(
                    SecurityEventLog.objects.filter(
                        event_type__in=["otp_verify_success", "otp_verify_failed"],
                        duration_ms__isnull=False,
                    ).aggregate(avg=models.Avg("duration_ms"))["avg"] or 0
                )
            ),
        },
        "recent_security_events": recent_events,
    }


def build_security_logs_context(*, event_type="", outcome="", order_id="", delivery_mode="", recent_limit=100):
    logs_qs = SecurityEventLog.objects.select_related("order", "actor").order_by("-created_at")

    if event_type:
        logs_qs = logs_qs.filter(event_type=event_type)
    if outcome:
        logs_qs = logs_qs.filter(outcome=outcome)
    if order_id:
        logs_qs = logs_qs.filter(order_id=order_id)
    if delivery_mode:
        logs_qs = logs_qs.filter(order__delivery_mode=delivery_mode)

    event_breakdown_qs = (
        logs_qs.values("event_type")
        .annotate(total=models.Count("id"))
        .order_by("event_type")
    )
    outcome_breakdown_qs = (
        logs_qs.values("outcome")
        .annotate(total=models.Count("id"))
        .order_by("outcome")
    )

    daily_window = timezone.now() - timezone.timedelta(days=6)
    daily_counts_qs = (
        logs_qs.filter(created_at__gte=daily_window)
        .annotate(day=models.functions.TruncDate("created_at"))
        .values("day")
        .annotate(total=models.Count("id"))
        .order_by("day")
    )

    daily_lookup = {entry["day"]: entry["total"] for entry in daily_counts_qs}
    daily_series = OrderedDict()
    for offset in range(7):
        day = (daily_window + timezone.timedelta(days=offset)).date()
        daily_series[day.strftime("%b %d")] = daily_lookup.get(day, 0)

    logs = [
        {
            "id": log.id,
            "event_type": log.event_type,
            "event_label": log.get_event_type_display(),
            "outcome": log.outcome,
            "order_id": log.order_id,
            "delivery_mode": log.order.delivery_mode if log.order else None,
            "delivery_mode_label": log.order.get_delivery_mode_display() if log.order else None,
            "actor_name": log.actor.username if log.actor else "System",
            "duration_ms": log.duration_ms,
            "details": log.details or {},
            "created_at": log.created_at,
        }
        for log in logs_qs[:recent_limit]
    ]

    avg_duration_ms = round(logs_qs.filter(duration_ms__isnull=False).aggregate(
        avg=models.Avg("duration_ms")
    )["avg"] or 0)

    return {
        "security_log_filters": {
            "event_type": event_type,
            "outcome": outcome,
            "order_id": order_id,
            "delivery_mode": delivery_mode,
        },
        "security_log_filter_options": {
            "event_types": SecurityEventLog.EVENT_CHOICES,
            "outcomes": SecurityEventLog.OUTCOME_CHOICES,
            "delivery_modes": Order.DELIVERY_MODE_CHOICES,
        },
        "security_log_stats": {
            "filtered_total": logs_qs.count(),
            "avg_duration_ms": avg_duration_ms,
            "success_count": logs_qs.filter(outcome="success").count(),
            "blocked_count": logs_qs.filter(outcome="blocked").count(),
            "failed_count": logs_qs.filter(outcome="failed").count(),
        },
        "security_log_chart_data": {
            "event_labels": [entry["event_type"].replace("_", " ").title() for entry in event_breakdown_qs],
            "event_values": [entry["total"] for entry in event_breakdown_qs],
            "outcome_labels": [entry["outcome"].title() for entry in outcome_breakdown_qs],
            "outcome_values": [entry["total"] for entry in outcome_breakdown_qs],
            "daily_labels": list(daily_series.keys()),
            "daily_values": list(daily_series.values()),
        },
        "security_logs": logs,
    }

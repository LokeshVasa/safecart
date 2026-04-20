import time

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from store.models import DeliveryAgent, Order
from store.services.security_service import (
    DeliverySecurityError,
    get_order_security_snapshot,
    log_security_event,
    validate_qr_scan_security,
)


class DeliveryQRScanError(Exception):
    status_code = 400


class DeliveryQRAssignmentError(DeliveryQRScanError):
    status_code = 403


def claim_order_from_token(*, token, user):
    started_at = time.perf_counter()

    if not token:
        raise DeliveryQRScanError("No token provided")

    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(token_value=token)
            delivery_agent, _ = DeliveryAgent.objects.get_or_create(user=user)

            if order.delivery_agent_id is not None and order.delivery_agent_id != delivery_agent.id:
                log_security_event(
                    order,
                    "qr_scan_blocked",
                    actor=user,
                    outcome="blocked",
                    details={
                        "reason": "assigned_to_another_agent",
                        "duration_ms": round((time.perf_counter() - started_at) * 1000),
                    },
                )
                raise DeliveryQRAssignmentError("This order is assigned to another delivery agent.")

            try:
                validate_qr_scan_security(order)
            except DeliverySecurityError as exc:
                log_security_event(
                    order,
                    "qr_scan_blocked",
                    actor=user,
                    outcome="blocked",
                    details={
                        "reason": str(exc),
                        "security_stage": get_order_security_snapshot(order)["security_stage"],
                        "duration_ms": round((time.perf_counter() - started_at) * 1000),
                    },
                )
                raise DeliveryQRScanError(str(exc)) from exc

            order.register_delivery_qr_scan()

            update_fields = ["qr_scan_count", "expires_at"]

            if order.delivery_agent_id is None:
                order.delivery_agent = delivery_agent
                update_fields.append("delivery_agent")

            if order.status in ["Pending", "Packed"]:
                order.status = "Shipped"
                update_fields.append("status")

            order.save(update_fields=update_fields)
            log_security_event(
                order,
                "qr_scan",
                actor=user,
                outcome="success",
                details={
                    "qr_scan_count": order.qr_scan_count,
                    "security_stage": get_order_security_snapshot(order)["security_stage"],
                    "duration_ms": round((time.perf_counter() - started_at) * 1000),
                },
            )
            return order
    except ObjectDoesNotExist as exc:
        raise Order.DoesNotExist from exc

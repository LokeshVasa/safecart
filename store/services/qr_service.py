from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from store.models import DeliveryAgent, Order


class DeliveryQRScanError(Exception):
    status_code = 400


class DeliveryQRAssignmentError(DeliveryQRScanError):
    status_code = 403


def claim_order_from_token(*, token, user):
    if not token:
        raise DeliveryQRScanError("No token provided")

    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(token_value=token)
            delivery_agent, _ = DeliveryAgent.objects.get_or_create(user=user)

            if order.delivery_agent_id is not None and order.delivery_agent_id != delivery_agent.id:
                raise DeliveryQRAssignmentError("This order is assigned to another delivery agent.")

            qr_error = order.get_delivery_qr_block_reason()
            if qr_error:
                raise DeliveryQRScanError(qr_error)

            order.register_delivery_qr_scan()

            update_fields = ["qr_scan_count", "expires_at"]

            if order.delivery_agent_id is None:
                order.delivery_agent = delivery_agent
                update_fields.append("delivery_agent")

            if order.status in ["Pending", "Packed"]:
                order.status = "Shipped"
                update_fields.append("status")

            order.save(update_fields=update_fields)
            return order
    except ObjectDoesNotExist as exc:
        raise Order.DoesNotExist from exc

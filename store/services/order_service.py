from datetime import timedelta

from store.models import Order
from store.services.security_service import get_order_security_snapshot


ORDER_STATUS_PRIORITY = {
    "Pending": 0,
    "Packed": 1,
    "Shipped": 2,
    "Delivered": 3,
    "Cancelled": 4,
}


def _serialize_order_items(order):
    return [
        {
            "name": item.product.name,
            "image": item.product.image,
            "quantity": item.quantity,
            "price": item.price,
        }
        for item in order.items.all()
    ]


def build_customer_orders_context(user):
    orders = (
        Order.objects.filter(user=user)
        .select_related("address", "delivery_agent")
        .prefetch_related("items__product")
        .order_by("-created_at")
    )

    orders_with_details = []
    for order in orders:
        items = _serialize_order_items(order)
        security = get_order_security_snapshot(order)
        orders_with_details.append({
            "id": order.id,
            "status": order.status,
            "date": order.created_at,
            "items": items,
            "total_amount": sum(i["price"] * i["quantity"] for i in items),
            "expected_delivery": order.created_at + timedelta(days=5),
            "address": order.address,
            "delivery_mode": order.delivery_mode,
            "can_track": order.status in ["Packed", "Shipped"] and order.delivery_agent_id is not None,
            "can_call": order.status in ["Packed", "Shipped"] and order.delivery_agent_id is not None,
            "can_handshake": (
                order.status in ["Pending", "Packed", "Shipped"]
                and order.delivery_agent_id is not None
                and order.delivery_mode == "secure"
            ),
            "handshake_requested": security["otp_active"] and not security["is_closed"],
            "can_cancel": order.status in ["Pending", "Packed"],
            "created_at": order.created_at,
            "security": security,
        })

    orders_with_details.sort(
        key=lambda order: (
            ORDER_STATUS_PRIORITY.get(order["status"], 99),
            -order["created_at"].timestamp()
        )
    )

    return {"orders": orders_with_details}


def build_seller_orders_context():
    orders = (
        Order.objects.all()
        .select_related("address")
        .prefetch_related("items__product")
        .order_by("-created_at")
    )

    orders_with_details = []
    for order in orders:
        items = _serialize_order_items(order)
        delivery_mode_label = dict(Order.DELIVERY_MODE_CHOICES).get(order.delivery_mode, order.delivery_mode)
        orders_with_details.append({
            "id": order.id,
            "status": order.status,
            "date": order.created_at,
            "items": items,
            "total_amount": sum(i["price"] * i["quantity"] for i in items),
            "expected_delivery": order.created_at + timedelta(days=5),
            "pincode": order.address.pincode,
            "token_": order.token_value,
            "can_print_qr": (
                order.delivery_mode == "secure"
                and order.status in ["Pending", "Packed", "Shipped"]
            ),
            "delivery_mode": order.delivery_mode,
            "delivery_mode_label": delivery_mode_label,
            "created_at": order.created_at,
        })

    orders_with_details.sort(
        key=lambda order: (
            ORDER_STATUS_PRIORITY.get(order["status"], 99),
            -order["created_at"].timestamp()
        )
    )

    return {
        "orders": orders_with_details,
        "stats": {
            "total_orders": len(orders_with_details),
            "pending_orders": sum(1 for order in orders_with_details if order["status"] == "Pending"),
            "active_orders": sum(1 for order in orders_with_details if order["status"] in ["Packed", "Shipped"]),
            "delivered_orders": sum(1 for order in orders_with_details if order["status"] == "Delivered"),
        },
    }

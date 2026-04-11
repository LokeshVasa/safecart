from django.db.models import Count, Q

from store.models import Order


DELIVERY_MODE_LABELS = {
    "secure": "SafeCart Secure",
    "traditional": "Traditional Delivery",
}


def build_delivery_comparison_context():
    mode_rows = []
    for mode_value, mode_label in Order.DELIVERY_MODE_CHOICES:
        qs = Order.objects.filter(delivery_mode=mode_value)
        total = qs.count()
        delivered = qs.filter(status="Delivered").count()
        cancelled = qs.filter(status="Cancelled").count()
        active = qs.exclude(status__in=["Delivered", "Cancelled"]).count()
        delivered_rate = round((delivered / total) * 100, 1) if total else 0

        mode_rows.append({
            "mode": mode_value,
            "label": mode_label,
            "total": total,
            "delivered": delivered,
            "cancelled": cancelled,
            "active": active,
            "delivered_rate": delivered_rate,
        })

    mode_breakdown = (
        Order.objects.values("delivery_mode")
        .annotate(total=Count("id"))
        .order_by("delivery_mode")
    )

    status_breakdown = (
        Order.objects.values("delivery_mode")
        .annotate(
            pending=Count("id", filter=Q(status="Pending")),
            packed=Count("id", filter=Q(status="Packed")),
            shipped=Count("id", filter=Q(status="Shipped")),
            delivered=Count("id", filter=Q(status="Delivered")),
            cancelled=Count("id", filter=Q(status="Cancelled")),
        )
        .order_by("delivery_mode")
    )

    status_by_mode = {
        row["delivery_mode"]: {
            "Pending": row["pending"],
            "Packed": row["packed"],
            "Shipped": row["shipped"],
            "Delivered": row["delivered"],
            "Cancelled": row["cancelled"],
        }
        for row in status_breakdown
    }

    mode_labels = [DELIVERY_MODE_LABELS.get(row["delivery_mode"], row["delivery_mode"].title()) for row in mode_breakdown]
    mode_totals = [row["total"] for row in mode_breakdown]

    comparison_highlights = {
        "secure_total": next((row["total"] for row in mode_rows if row["mode"] == "secure"), 0),
        "traditional_total": next((row["total"] for row in mode_rows if row["mode"] == "traditional"), 0),
        "secure_delivered_rate": next((row["delivered_rate"] for row in mode_rows if row["mode"] == "secure"), 0),
        "traditional_delivered_rate": next((row["delivered_rate"] for row in mode_rows if row["mode"] == "traditional"), 0),
    }

    return {
        "delivery_comparison_rows": mode_rows,
        "delivery_comparison_highlights": comparison_highlights,
        "delivery_comparison_chart_data": {
            "mode_labels": mode_labels,
            "mode_totals": mode_totals,
            "status_labels": ["Pending", "Packed", "Shipped", "Delivered", "Cancelled"],
            "secure_status_values": [status_by_mode.get("secure", {}).get(label, 0) for label in ["Pending", "Packed", "Shipped", "Delivered", "Cancelled"]],
            "traditional_status_values": [status_by_mode.get("traditional", {}).get(label, 0) for label in ["Pending", "Packed", "Shipped", "Delivered", "Cancelled"]],
        },
    }

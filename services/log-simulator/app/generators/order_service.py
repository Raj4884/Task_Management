"""Order-service log generator.

Produces realistic order-lifecycle log messages covering order creation,
inventory checks, fulfilment, shipping, and status transitions.
"""

from __future__ import annotations

import random
import uuid
from typing import Any

from faker import Faker

from app.generators.base import BaseLogGenerator

fake = Faker()

# ---------------------------------------------------------------------------
# Domain-specific message pools
# ---------------------------------------------------------------------------

_INFO_MESSAGES: list[str] = [
    "Order {order} created by customer {cust} – {items} item(s), ${total}",
    "Inventory reserved for order {order}: {items} SKU(s)",
    "Order {order} status changed: {from_status} → {to_status}",
    "Shipping label generated for order {order} via {carrier}",
    "Order {order} dispatched – tracking: {tracking}",
    "Order {order} delivered to {city}, {country}",
    "Return initiated for order {order}: reason={return_reason}",
    "Order {order} cancelled by customer – refund initiated",
    "Bulk import processed: {count} orders ingested",
    "Order {order} fulfilled from warehouse {warehouse}",
]

_DEBUG_MESSAGES: list[str] = [
    "Cart {cart} converted to order {order}",
    "Inventory check for SKU {sku}: available={available}, requested={requested}",
    "Discount code '{code}' applied: -${discount}",
    "Shipping rate calculation for {weight}kg to {country}: ${rate}",
    "Tax nexus determined: {region} ({tax_pct}%)",
    "Order validation passed: {checks} checks in {ms}ms",
    "Fulfilment queue depth: {depth} orders pending",
]

_WARN_MESSAGES: list[str] = [
    "Low inventory for SKU {sku}: {available} remaining (threshold: {threshold})",
    "Order {order} total exceeds fraud-review threshold: ${total}",
    "Shipping estimate unavailable for destination {country} – using fallback",
    "Order {order} stuck in '{status}' for {hours} hours",
    "Duplicate order submission detected from session {session}",
    "Partial fulfilment for order {order}: {fulfilled}/{items} items shipped",
    "Carrier API response degraded: {ms}ms latency",
]

_ERROR_MESSAGES: list[str] = [
    "Out of stock: SKU {sku} unavailable for order {order}",
    "Shipping label creation failed: {reason} for order {order}",
    "Order validation error: {detail} in order {order}",
    "Database timeout during order write: {ms}ms (order {order})",
    "Payment confirmation not received for order {order} – retry {n}/{max}",
    "Fulfilment API returned HTTP {status} for order {order}",
    "Inventory sync conflict: expected={expected}, actual={actual} for SKU {sku}",
    "Address verification failed for order {order}: {reason}",
]

_FATAL_MESSAGES: list[str] = [
    "FATAL: Order database replication lag exceeds 30s – writes suspended",
    "FATAL: Inventory service circuit breaker OPEN – order creation halted",
    "FATAL: Corrupt order data detected in batch {batch} – manual triage needed",
]

_TRACE_MESSAGES: list[str] = [
    "TRACE: Order payload deserialised: {bytes} bytes",
    "TRACE: Inventory lock acquired for SKUs: {skus}",
    "TRACE: Entering saga step '{step}' for order {order}",
]


class OrderServiceGenerator(BaseLogGenerator):
    """Generates realistic log entries for an order management service."""

    service_name: str = "order-service"

    def _service_messages(self, level: str) -> list[str]:
        return {
            "INFO": _INFO_MESSAGES,
            "DEBUG": _DEBUG_MESSAGES,
            "WARN": _WARN_MESSAGES,
            "ERROR": _ERROR_MESSAGES,
            "FATAL": _FATAL_MESSAGES,
            "TRACE": _TRACE_MESSAGES,
        }.get(level, _INFO_MESSAGES)

    def _service_metadata(self, level: str) -> dict[str, Any]:
        items = random.randint(1, 12)
        meta: dict[str, Any] = {
            "order_id": f"ord_{uuid.uuid4().hex[:8]}",
            "items_count": items,
            "total_amount": round(random.uniform(9.99, 4999.99), 2),
            "shipping_method": random.choice([
                "standard", "express", "next_day", "economy", "pickup",
            ]),
        }
        if level in ("ERROR", "FATAL"):
            meta["error_code"] = random.choice([
                "OUT_OF_STOCK", "SHIPPING_FAILED", "VALIDATION_ERROR",
                "DB_TIMEOUT", "PAYMENT_PENDING", "FULFILMENT_ERROR",
            ])
        return meta

    def _render_template(self, template: str) -> str:
        order_replacements: dict[str, str] = {
            "{order}": f"ord_{uuid.uuid4().hex[:8]}",
            "{cust}": f"cust_{uuid.uuid4().hex[:8]}",
            "{items}": str(random.randint(1, 12)),
            "{total}": f"{random.uniform(15, 5000):.2f}",
            "{from_status}": random.choice(["pending", "confirmed", "processing"]),
            "{to_status}": random.choice(["confirmed", "processing", "shipped", "delivered"]),
            "{carrier}": random.choice(["UPS", "FedEx", "DHL", "USPS", "Royal Mail"]),
            "{tracking}": fake.bothify("??##########??").upper(),
            "{city}": fake.city(),
            "{country}": fake.country_code(),
            "{return_reason}": random.choice([
                "wrong_size", "damaged", "not_as_described", "changed_mind",
            ]),
            "{count}": str(random.randint(50, 5000)),
            "{warehouse}": random.choice(["WH-US-EAST", "WH-US-WEST", "WH-EU-CENTRAL"]),
            "{cart}": f"cart_{uuid.uuid4().hex[:8]}",
            "{sku}": fake.bothify("SKU-####-??").upper(),
            "{available}": str(random.randint(0, 500)),
            "{requested}": str(random.randint(1, 20)),
            "{code}": random.choice(["SAVE20", "WELCOME10", "FREESHIP", "VIP30"]),
            "{discount}": f"{random.uniform(1, 100):.2f}",
            "{weight}": f"{random.uniform(0.1, 30):.1f}",
            "{rate}": f"{random.uniform(3.99, 49.99):.2f}",
            "{region}": random.choice(["US-CA", "US-NY", "EU-DE", "GB"]),
            "{tax_pct}": f"{random.uniform(5, 25):.1f}",
            "{checks}": str(random.randint(3, 12)),
            "{depth}": str(random.randint(10, 10000)),
            "{threshold}": str(random.choice([10, 25, 50, 100])),
            "{hours}": str(random.randint(1, 48)),
            "{session}": uuid.uuid4().hex[:12],
            "{fulfilled}": str(random.randint(1, 5)),
            "{expected}": str(random.randint(50, 500)),
            "{actual}": str(random.randint(0, 49)),
            "{batch}": f"batch_{random.randint(1000, 9999)}",
            "{skus}": ", ".join(fake.bothify("SKU-####-??").upper() for _ in range(random.randint(1, 4))),
            "{step}": random.choice(["reserve_inventory", "charge_payment", "create_shipment"]),
            "{reason}": random.choice([
                "address_invalid", "carrier_unavailable", "weight_exceeded",
                "customs_restriction",
            ]),
            "{detail}": random.choice([
                "missing shipping address", "invalid quantity for line item 3",
                "coupon expired", "unknown SKU",
            ]),
        }
        result = template
        for ph, val in order_replacements.items():
            if ph in result:
                result = result.replace(ph, val, 1)
        return super()._render_template(result)

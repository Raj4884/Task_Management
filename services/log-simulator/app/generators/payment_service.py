"""Payment-service log generator.

Produces realistic payment-processing log messages covering
payment authorisation, refunds, subscriptions, webhooks,
and fraud detection.
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
    "Payment {txn} authorised for ${amount} {currency} via {method}",
    "Refund {txn} processed: ${amount} {currency} returned to customer",
    "Subscription {sub_id} renewed – next billing {next_date}",
    "Webhook received from payment gateway: event={event}",
    "Payout batch {batch} dispatched – {count} transfers totalling ${amount}",
    "Invoice {inv} finalised for customer {cust}",
    "Payment intent {pi} created for ${amount} {currency}",
    "3-D Secure challenge completed for {txn}",
    "Recurring charge ${amount} applied to subscription {sub_id}",
    "Customer {cust} payment method updated to {method}",
]

_DEBUG_MESSAGES: list[str] = [
    "Stripe API call: POST /v1/charges – {ms}ms",
    "Idempotency key check: {key} – {result}",
    "Currency conversion: {from_c} → {to_c} at rate {rate}",
    "Tax calculation for region '{region}': ${tax}",
    "Payment retry scheduled: attempt {n} in {delay}s",
    "Webhook signature verified (algo=hmac-sha256)",
    "Ledger entry created: debit={debit}, credit={credit}",
]

_WARN_MESSAGES: list[str] = [
    "Payment gateway response slow: {ms}ms for {txn}",
    "Duplicate webhook received for event {event} – skipping",
    "Card expiry approaching for customer {cust}: {exp_date}",
    "Partial payment received for invoice {inv}: ${amount} of ${total}",
    "Refund amount ${amount} exceeds original charge – manual review required",
    "Subscription {sub_id} past due – grace period {days} days",
    "High transaction volume: {tps} TPS (threshold: {threshold})",
]

_ERROR_MESSAGES: list[str] = [
    "Payment declined: {decline_reason} for {txn} (${amount} {currency})",
    "Gateway timeout after {ms}ms for payment {txn}",
    "Insufficient funds for charge ${amount} on card ending {last4}",
    "Fraud detection flagged transaction {txn}: risk_score={score}",
    "Webhook delivery failed: HTTP {status} from {url}",
    "Subscription billing failed for {sub_id}: {reason}",
    "Refund processing error: {reason} for {txn}",
    "PCI token vault unreachable – cannot decrypt card data",
    "Double-charge detected for order {order}: ${amount} × 2",
]

_FATAL_MESSAGES: list[str] = [
    "FATAL: Payment ledger out of balance – reconciliation required",
    "FATAL: PCI vault credentials expired – all card operations halted",
    "FATAL: Database deadlock on transactions table – service degraded",
]

_TRACE_MESSAGES: list[str] = [
    "TRACE: Raw gateway response: {bytes} bytes",
    "TRACE: Webhook payload hash: {hash}",
    "TRACE: Entering idempotent transaction block for {txn}",
]


class PaymentServiceGenerator(BaseLogGenerator):
    """Generates realistic log entries for a payment processing service."""

    service_name: str = "payment-service"

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
        amount = round(random.uniform(1.00, 9999.99), 2)
        meta: dict[str, Any] = {
            "transaction_id": uuid.uuid4().hex[:12],
            "amount": amount,
            "currency": random.choice(["USD", "EUR", "GBP", "CAD", "AUD"]),
            "payment_method": random.choice([
                "credit_card", "debit_card", "paypal", "apple_pay",
                "google_pay", "bank_transfer", "crypto",
            ]),
        }
        if level in ("ERROR", "FATAL"):
            meta["error_code"] = random.choice([
                "CARD_DECLINED", "GATEWAY_TIMEOUT", "INSUFFICIENT_FUNDS",
                "FRAUD_FLAGGED", "PROCESSING_ERROR", "VAULT_UNREACHABLE",
            ])
            meta["decline_reason"] = random.choice([
                "do_not_honor", "insufficient_funds", "lost_card",
                "expired_card", "fraud_suspected", "processing_error",
            ])
        return meta

    def _render_template(self, template: str) -> str:
        amount = f"{random.uniform(5, 5000):.2f}"
        pay_replacements: dict[str, str] = {
            "{txn}": f"txn_{uuid.uuid4().hex[:10]}",
            "{amount}": amount,
            "{currency}": random.choice(["USD", "EUR", "GBP"]),
            "{method}": random.choice(["visa", "mastercard", "paypal", "apple_pay"]),
            "{sub_id}": f"sub_{uuid.uuid4().hex[:8]}",
            "{next_date}": fake.future_date(end_date="+60d").isoformat(),
            "{event}": random.choice([
                "payment_intent.succeeded", "charge.refunded",
                "invoice.paid", "subscription.updated",
            ]),
            "{batch}": f"batch_{random.randint(1000, 9999)}",
            "{count}": str(random.randint(10, 500)),
            "{inv}": f"inv_{uuid.uuid4().hex[:8]}",
            "{cust}": f"cust_{uuid.uuid4().hex[:8]}",
            "{pi}": f"pi_{uuid.uuid4().hex[:12]}",
            "{key}": uuid.uuid4().hex[:16],
            "{result}": random.choice(["new", "duplicate"]),
            "{from_c}": "USD",
            "{to_c}": random.choice(["EUR", "GBP", "JPY"]),
            "{rate}": f"{random.uniform(0.5, 1.5):.4f}",
            "{region}": random.choice(["US-CA", "EU-DE", "GB", "AU-NSW"]),
            "{tax}": f"{random.uniform(0.5, 200):.2f}",
            "{delay}": str(random.choice([5, 15, 30, 60])),
            "{exp_date}": fake.credit_card_expire(start="now", end="+3m"),
            "{total}": f"{random.uniform(100, 10000):.2f}",
            "{days}": str(random.randint(1, 14)),
            "{tps}": str(random.randint(100, 5000)),
            "{threshold}": str(random.choice([500, 1000, 2000])),
            "{decline_reason}": random.choice([
                "do_not_honor", "insufficient_funds", "expired_card",
            ]),
            "{last4}": fake.credit_card_number()[-4:],
            "{score}": f"{random.uniform(0.7, 1.0):.2f}",
            "{url}": fake.url(),
            "{reason}": random.choice([
                "gateway_error", "card_expired", "network_timeout",
                "invalid_amount", "currency_mismatch",
            ]),
            "{order}": f"ord_{uuid.uuid4().hex[:8]}",
            "{hash}": uuid.uuid4().hex[:16],
            "{debit}": amount,
            "{credit}": amount,
        }
        result = template
        for ph, val in pay_replacements.items():
            if ph in result:
                result = result.replace(ph, val, 1)
        return super()._render_template(result)

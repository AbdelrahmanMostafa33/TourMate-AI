"""
Stripe webhooks — async event processing for the booking payment pipeline.

This module handles Stripe webhook events for the Hybrid Booking System:
  - ``payment_intent.succeeded``  → marks Payment completed, confirms Booking
  - ``payment_intent.payment_failed`` → marks Payment as failed (booking stays pending)
  - ``charge.refunded``           → marks Payment refunded, cancels Booking

The endpoint:
  - Reads the **raw request body** (required for signature verification)
  - Verifies the Stripe signature using ``STRIPE_WEBHOOK_SECRET``
  - Dispatches events to ``BookingService`` handlers
  - Returns ``200`` to Stripe promptly (heavy work is done inline — the
    handlers are fast DB operations)

Security:
  - This endpoint is intentionally **unauthenticated** — Stripe does not
    send Bearer tokens.  Signature verification is the sole auth mechanism.
  - If ``STRIPE_WEBHOOK_SECRET`` is not configured, the endpoint returns
    ``501 Not Implemented``.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.services.booking_service import BookingService

logger = logging.getLogger(__name__)

router = APIRouter()

# Attempt to import Stripe at module level so we can fail gracefully
try:
    import stripe as stripe_lib
    _stripe_available = True
except ImportError:
    stripe_lib = None  # type: ignore[assignment]
    _stripe_available = False


# ═══════════════════════════════════════════════════════════════════════════════
# POST /stripe
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive and process Stripe webhook events.

    Stripe sends events as POST requests with a ``Stripe-Signature`` header.
    This endpoint:
      1. Reads the raw body
      2. Verifies the signature via ``stripe.Webhook.construct_event()``
      3. Routes the event to the appropriate ``BookingService`` handler
      4. Returns ``{"status": "ok"}``

    Returns:
        - ``200`` with ``{"status": "ok"}`` on successful processing
        - ``400`` if the signature is invalid or the event is unhandled
        - ``501`` if ``STRIPE_WEBHOOK_SECRET`` or the Stripe SDK is not configured
    """
    # ── Guard: webhook secret must be configured ──────────────────────────
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=501,
            detail="Stripe webhook secret not configured (STRIPE_WEBHOOK_SECRET)",
        )

    if not _stripe_available:
        raise HTTPException(
            status_code=501,
            detail="Stripe SDK not installed (pip install stripe)",
        )

    # ── Read raw body ────────────────────────────────────────────────────
    payload = await request.body()
    stripe_signature = request.headers.get("stripe-signature")

    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    # ── Verify signature and construct event ──────────────────────────────
    try:
        event = stripe_lib.Webhook.construct_event(
            payload,
            stripe_signature,
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        logger.warning("[StripeWebhook] Invalid payload")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe_lib.error.SignatureVerificationError:
        logger.warning("[StripeWebhook] Invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    data_object = event["data"]["object"]

    # ── Extract PaymentIntent ID (varies by event type) ──────────────────
    #   payment_intent.* events:  data.object.id is the PI ID
    #   charge.* events:          data.object.payment_intent is the PI ID
    if event_type == "charge.refunded":
        stripe_pi_id = data_object.get("payment_intent", "")
    else:
        stripe_pi_id = data_object.get("id", "")

    if not stripe_pi_id:
        logger.warning(
            "[StripeWebhook] Could not extract PaymentIntent ID from event=%s",
            event_type,
        )
        raise HTTPException(
            status_code=400,
            detail=f"No PaymentIntent ID found in event '{event_type}'",
        )

    logger.info(
        "[StripeWebhook] Received event type=%s PI=%s",
        event_type, stripe_pi_id,
    )

    # ── Route event to service handler ────────────────────────────────────
    svc = BookingService(db)

    try:
        if event_type == "payment_intent.succeeded":
            result = await svc.handle_webhook_payment_succeeded(stripe_pi_id)

        elif event_type == "payment_intent.payment_failed":
            result = await svc.handle_webhook_payment_failed(stripe_pi_id)

        elif event_type == "charge.refunded":
            result = await svc.handle_webhook_charge_refunded(stripe_pi_id)

        else:
            # Acknowledge receipt but don't error — Stripe expects 200 for
            # unhandled event types (e.g. ``payment_intent.created``).
            logger.info(
                "[StripeWebhook] Unhandled event type '%s' — acknowledged",
                event_type,
            )
            await db.commit()
            return {"status": "ignored", "event_type": event_type}

    except ValueError as exc:
        logger.error(
            "[StripeWebhook] Error processing event %s: %s",
            event_type, exc,
        )
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()

    logger.info(
        "[StripeWebhook] Processed %s → booking %s (status=%s)",
        event_type, result.get("booking_id", "?"), result.get("status", "?"),
    )

    return {"status": "ok", "event_type": event_type, **result}

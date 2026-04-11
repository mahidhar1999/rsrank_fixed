import hmac
import hashlib
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.engine import Connection
from app.db import get_db
from app.dependencies import get_current_user
from app.schemas import CreateOrderRequest, CreateOrderResponse, VerifyPaymentRequest
from app.config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, PLAN_AMOUNT_INR

router = APIRouter()


def _get_razorpay_client():
    import razorpay

    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise Exception("Razorpay keys not configured")

    return razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


@router.post("/create-order", response_model=CreateOrderResponse)
def create_order(
    body: CreateOrderRequest,
    current_user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    if body.plan not in PLAN_AMOUNT_INR:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {body.plan}")

    amount = PLAN_AMOUNT_INR[body.plan]
    client = _get_razorpay_client()
    try:
        print("PLAN:", body.plan)
        print("USER:", current_user)

        print("KEY_ID:", RAZORPAY_KEY_ID)

        client = _get_razorpay_client()

        order = client.order.create({
            "amount": amount,
            "currency": "INR",
            "receipt": f"rsrank_{current_user['id']}_{int(datetime.now().timestamp())}",
            "notes": {"plan": body.plan, "user_id": str(current_user["id"])},
        })

        print("ORDER CREATED:", order)

        db.execute(text("""
            INSERT INTO payments (user_id, razorpay_order_id, amount, currency, plan, status)
            VALUES (:uid, :oid, :amount, 'INR', :plan, 'created')
            ON CONFLICT (razorpay_order_id) DO NOTHING
        """), {
            "uid": current_user["id"],
            "oid": order["id"],
            "amount": amount / 100,
            "plan": body.plan,
        })

        db.commit()

        return CreateOrderResponse(
            order_id=order["id"],
            amount=amount,
            currency="INR",
            key_id=RAZORPAY_KEY_ID,
        )

    except Exception as e:
        print("🔥 FULL ERROR:", str(e))
        return {
            "error": str(e),
            "debug": {
                "key_id": RAZORPAY_KEY_ID,
                "key_secret_present": bool(RAZORPAY_KEY_SECRET),
                "plan": body.plan,
                "amount": amount,
            }
        }
    
@router.post("/verify")
def verify_payment(
    body: VerifyPaymentRequest,
    current_user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    """Frontend calls this after Razorpay checkout success."""
    # Verify HMAC signature
    msg = f"{body.razorpay_order_id}|{body.razorpay_payment_id}"
    expected = hmac.new(
        RAZORPAY_KEY_SECRET.encode(), msg.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, body.razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid payment signature")

    valid_until = datetime.now(timezone.utc) + timedelta(days=30)

    # Update payment record
    db.execute(text("""
        UPDATE payments
        SET status = 'paid',
            razorpay_payment_id = :pid,
            razorpay_signature  = :sig
        WHERE razorpay_order_id = :oid AND user_id = :uid
    """), {
        "pid": body.razorpay_payment_id, "sig": body.razorpay_signature,
        "oid": body.razorpay_order_id,   "uid": current_user["id"],
    })

    # Activate subscription
    db.execute(text("""
        UPDATE users
        SET plan                = :plan,
            subscription_status = 'active',
            valid_until         = :valid_until,
            updated_at          = NOW()
        WHERE id = :uid
    """), {"plan": body.plan, "valid_until": valid_until, "uid": current_user["id"]})
    db.commit()

    return {"status": "success", "plan": body.plan, "valid_until": str(valid_until.date())}


@router.post("/webhook")
async def razorpay_webhook(request: Request, db: Connection = Depends(get_db)):
    """Razorpay server-side webhook for subscription events."""
    body_bytes = await request.body()
    signature  = request.headers.get("X-Razorpay-Signature", "")

    expected = hmac.new(
        RAZORPAY_KEY_SECRET.encode(), body_bytes, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    import json
    event = json.loads(body_bytes)
    event_type = event.get("event", "")

    if event_type == "payment.captured":
        payment = event["payload"]["payment"]["entity"]
        notes   = payment.get("notes", {})
        user_id = notes.get("user_id")
        plan    = notes.get("plan", "pro")

        if user_id:
            valid_until = datetime.now(timezone.utc) + timedelta(days=30)
            db.execute(text("""
                UPDATE users
                SET plan = :plan, subscription_status = 'active', valid_until = :vu
                WHERE id = :uid
            """), {"plan": plan, "vu": valid_until, "uid": int(user_id)})
            db.commit()

    elif event_type in ("subscription.cancelled", "subscription.expired"):
        sub = event["payload"]["subscription"]["entity"]
        # Handle cancellation — look up by razorpay subscription_id
        db.execute(text("""
            UPDATE users SET subscription_status = 'cancelled'
            WHERE subscription_id = :sid
        """), {"sid": sub.get("id")})
        db.commit()

    return {"status": "ok"}

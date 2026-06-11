import os
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Set, Optional

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from database import get_db, engine, Base, SessionLocal
import models
import schemas
from seed import seed_db

app = FastAPI(title="Real-Time Ticket Booking System")

# Enable CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create frontend folder if it doesn't exist so StaticFiles doesn't error
os.makedirs("/frontend", exist_ok=True)
os.makedirs("frontend", exist_ok=True)

# Helper function to auto-expire locked seats in database
def check_and_expire_locks(db: Session, show_id: int):
    now = datetime.utcnow()
    # Find show seats locked but expired
    expired_seats = db.query(models.ShowSeat).filter(
        models.ShowSeat.show_id == show_id,
        models.ShowSeat.status == "Locked",
        models.ShowSeat.locked_until < now
    ).all()
    
    if expired_seats:
        for seat in expired_seats:
            seat.status = "Available"
            seat.locked_until = None
        db.commit()
        return True
    return False


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        # Maps show_id to a set of active WebSockets
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, show_id: int):
        await websocket.accept()
        if show_id not in self.active_connections:
            self.active_connections[show_id] = set()
        self.active_connections[show_id].add(websocket)

    def disconnect(self, websocket: WebSocket, show_id: int):
        if show_id in self.active_connections:
            self.active_connections[show_id].remove(websocket)
            if not self.active_connections[show_id]:
                del self.active_connections[show_id]

    async def broadcast_to_show(self, show_id: int, message: dict):
        if show_id in self.active_connections:
            # Create a copy of the connection set to avoid mutation during iteration
            for connection in list(self.active_connections[show_id]):
                try:
                    await connection.send_text(json.dumps(message))
                except Exception:
                    # Connection might be closed, clean it up
                    self.disconnect(connection, show_id)

manager = ConnectionManager()


# REST APIs
@app.post("/api/db/reset")
def reset_database():
    """Drops all tables and seeds mock data for demonstration."""
    try:
        seed_db()
        return {"status": "success", "message": "Database reset and seeded successfully."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset database: {str(e)}"
        )


@app.get("/api/users", response_model=List[schemas.UserResponse])
def get_users(db: Session = Depends(get_db)):
    return db.query(models.User).order_by(models.User.user_id).all()


@app.get("/api/shows", response_model=List[schemas.ShowResponse])
def get_shows(db: Session = Depends(get_db)):
    results = db.query(
        models.Show.show_id,
        models.Show.event_id,
        models.Event.title.label("event_title"),
        models.Event.event_type.label("event_type"),
        models.Show.venue_id,
        models.Venue.name.label("venue_name"),
        models.Venue.location.label("venue_location"),
        models.Show.start_time,
        models.Show.end_time,
        models.Show.base_price
    ).join(models.Event, models.Show.event_id == models.Event.event_id) \
     .join(models.Venue, models.Show.venue_id == models.Venue.venue_id) \
     .order_by(models.Show.start_time).all()
    
    return results


@app.get("/api/shows/{show_id}/seats", response_model=List[schemas.ShowSeatResponse])
async def get_show_seats(show_id: int, db: Session = Depends(get_db)):
    # Run lazy lock expiry check before returning seats
    locks_expired = check_and_expire_locks(db, show_id)
    
    # Query all seats with tier details
    seats = db.query(
        models.ShowSeat.show_seat_id,
        models.ShowSeat.show_id,
        models.ShowSeat.seat_id,
        models.Seat.seat_number,
        models.Seat.row_num,
        models.SeatTier.tier_name,
        models.SeatTier.multiplier,
        models.ShowSeat.final_price,
        models.ShowSeat.status,
        models.ShowSeat.locked_until
    ).join(models.Seat, models.ShowSeat.seat_id == models.Seat.seat_id) \
     .outerjoin(models.SeatTier, models.Seat.tier_id == models.SeatTier.tier_id) \
     .filter(models.ShowSeat.show_id == show_id) \
     .order_by(models.Seat.row_num, models.Seat.seat_number).all()

    # Format output
    response_list = []
    for s in seats:
        multiplier = s.multiplier if s.multiplier is not None else Decimal("1.00")
        response_list.append({
            "show_seat_id": s.show_seat_id,
            "show_id": s.show_id,
            "seat_id": s.seat_id,
            "seat_number": s.seat_number,
            "row_num": s.row_num,
            "tier_name": s.tier_name,
            "multiplier": multiplier,
            "final_price": s.final_price,
            "status": s.status,
            "locked_until": s.locked_until
        })
        
    # If locks expired, broadcast to all connected web sockets
    if locks_expired:
        await manager.broadcast_to_show(show_id, {"event": "seats_expired", "show_id": show_id})

    return response_list


@app.post("/api/coupons/validate")
def validate_coupon(code: str, base_amount: float, db: Session = Depends(get_db)):
    now = datetime.utcnow()
    coupon = db.query(models.Coupon).filter(
        models.Coupon.code == code,
        models.Coupon.is_active == True,
        models.Coupon.expiry_date > now
    ).first()
    
    if not coupon:
        raise HTTPException(status_code=400, detail="Invalid or expired coupon code.")
    
    discount = Decimal("0.00")
    base_dec = Decimal(str(base_amount))
    if coupon.discount_type == "Flat":
        discount = coupon.discount_value
    elif coupon.discount_type == "Percentage":
        discount = base_dec * (coupon.discount_value / Decimal("100.00"))
        if coupon.max_discount is not None:
            discount = min(discount, coupon.max_discount)
            
    # Cap discount at base amount
    discount = min(discount, base_dec)
    
    return {
        "coupon_id": coupon.coupon_id,
        "code": coupon.code,
        "discount_type": coupon.discount_type,
        "discount_value": coupon.discount_value,
        "discount_amount": discount,
        "final_amount": base_dec - discount
    }


@app.post("/api/bookings", response_model=schemas.BookingResponse)
async def create_booking(payload: schemas.CreateBookingRequest, db: Session = Depends(get_db)):
    """
    Creates a booking using a strict ACID-compliant transaction with row-level read blocks
    (`SELECT ... FOR UPDATE`) on the queried show seats.
    """
    # 1. Start isolated transaction block
    try:
        # Fetch show and lock corresponding rows in show_seats
        show = db.query(models.Show).filter(models.Show.show_id == payload.show_id).first()
        if not show:
            raise HTTPException(status_code=404, detail="Show not found.")

        # Ensure user exists
        user = db.query(models.User).filter(models.User.user_id == payload.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        # Perform row-level locking on target seats for this show
        show_seats = db.query(models.ShowSeat).filter(
            models.ShowSeat.show_id == payload.show_id,
            models.ShowSeat.seat_id.in_(payload.seat_ids)
        ).with_for_update().all()

        if len(show_seats) != len(payload.seat_ids):
            raise HTTPException(status_code=400, detail="One or more selected seats do not exist for this show.")

        # Validate availability of each locked seat
        now = datetime.utcnow()
        for ss in show_seats:
            # Re-verify lock expiration on the spot
            if ss.status == "Locked" and ss.locked_until and ss.locked_until < now:
                ss.status = "Available"
                ss.locked_until = None
            
            # Seat must be either Available or Locked (any locking status is cleared upon purchase by the user)
            if ss.status == "Booked":
                raise HTTPException(status_code=400, detail=f"Seat ID {ss.seat_id} is already booked.")
            
            # Note: For simple multi-tab simulation, we let the user who locked it book it. 
            # If it's locked by another user and not expired, block it.
            # We don't save the locking user_id in schema, so we treat any active lock as valid 
            # if within the lock window, but for this transaction let's allow bookings if they bypass lock check.
            # In a full app, we would compare locking session. Here, we'll confirm that seats are either Available or Locked.
        
        # Calculate pricing
        subtotal = Decimal("0.00")
        seat_details = []
        for ss in show_seats:
            # Load seat details
            seat = db.query(models.Seat).filter(models.Seat.seat_id == ss.seat_id).first()
            tier = db.query(models.SeatTier).filter(models.SeatTier.tier_id == seat.tier_id).first() if seat.tier_id else None
            multiplier = tier.multiplier if tier else Decimal("1.00")
            
            seat_price = show.base_price * multiplier
            ss.final_price = seat_price
            subtotal += seat_price
            
            seat_details.append({
                "seat_id": ss.seat_id,
                "seat_number": seat.seat_number,
                "row_num": seat.row_num,
                "final_price": seat_price
            })

        # Apply coupon if provided
        coupon_id = None
        discount = Decimal("0.00")
        if payload.coupon_code:
            coupon = db.query(models.Coupon).filter(
                models.Coupon.code == payload.coupon_code,
                models.Coupon.is_active == True,
                models.Coupon.expiry_date > now
            ).first()
            
            if coupon:
                coupon_id = coupon.coupon_id
                if coupon.discount_type == "Flat":
                    discount = coupon.discount_value
                elif coupon.discount_type == "Percentage":
                    discount = subtotal * (coupon.discount_value / Decimal("100.00"))
                    if coupon.max_discount is not None:
                        discount = min(discount, coupon.max_discount)
                discount = min(discount, subtotal)

        total_amount = subtotal - discount

        # Create booking entry
        booking = models.Booking(
            user_id=payload.user_id,
            show_id=payload.show_id,
            coupon_id=coupon_id,
            total_amount=total_amount,
            status="Confirmed"
        )
        db.add(booking)
        db.flush() # get booking_id

        # Update seat states
        for ss in show_seats:
            ss.status = "Booked"
            ss.booking_id = booking.booking_id
            ss.locked_until = None

        db.commit()

        # Fetch details for serialization
        event = db.query(models.Event).filter(models.Event.event_id == show.event_id).first()
        venue = db.query(models.Venue).filter(models.Venue.venue_id == show.venue_id).first()

        response = {
            "booking_id": booking.booking_id,
            "user_id": booking.user_id,
            "show_id": booking.show_id,
            "event_title": event.title,
            "venue_name": venue.name,
            "start_time": show.start_time,
            "total_amount": total_amount,
            "status": booking.status,
            "created_at": booking.created_at,
            "seats": seat_details
        }

        # Broadcast the seat update to all connected WebSockets
        await manager.broadcast_to_show(payload.show_id, {
            "event": "seats_updated",
            "show_id": payload.show_id,
            "status": "Booked",
            "seat_ids": payload.seat_ids
        })

        return response

    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Booking transaction failed: {str(e)}")


# WebSockets Server Endpoint
@app.websocket("/ws/shows/{show_id}")
async def websocket_endpoint(websocket: WebSocket, show_id: int):
    await manager.connect(websocket, show_id)
    db: Session = SessionLocal()
    
    try:
        while True:
            # Wait for messages from client (lock/unlock commands)
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                action = message.get("action") # "lock" or "unlock"
                seat_ids = message.get("seat_ids", [])
                user_id = message.get("user_id")

                if not action or not seat_ids or not user_id:
                    continue

                now = datetime.utcnow()
                updated_seats = []
                
                # Use short locking transaction for seat holds
                if action == "lock":
                    # Lock seats for 60 seconds
                    lock_duration = timedelta(seconds=60)
                    locked_until = now + lock_duration
                    
                    # Transactional hold
                    show_seats = db.query(models.ShowSeat).filter(
                        models.ShowSeat.show_id == show_id,
                        models.ShowSeat.seat_id.in_(seat_ids)
                    ).with_for_update().all()
                    
                    valid_to_lock = []
                    for ss in show_seats:
                        # Clean up expired locks first
                        if ss.status == "Locked" and ss.locked_until and ss.locked_until < now:
                            ss.status = "Available"
                            ss.locked_until = None
                        
                        if ss.status == "Available":
                            ss.status = "Locked"
                            ss.locked_until = locked_until
                            valid_to_lock.append(ss.seat_id)
                    
                    db.commit()
                    
                    if valid_to_lock:
                        # Broadcast lock to everyone
                        await manager.broadcast_to_show(show_id, {
                            "event": "seats_updated",
                            "show_id": show_id,
                            "status": "Locked",
                            "seat_ids": valid_to_lock,
                            "locked_until": locked_until.isoformat()
                        })

                elif action == "unlock":
                    show_seats = db.query(models.ShowSeat).filter(
                        models.ShowSeat.show_id == show_id,
                        models.ShowSeat.seat_id.in_(seat_ids),
                        models.ShowSeat.status == "Locked"
                    ).with_for_update().all()
                    
                    valid_to_unlock = []
                    for ss in show_seats:
                        ss.status = "Available"
                        ss.locked_until = None
                        valid_to_unlock.append(ss.seat_id)
                        
                    db.commit()
                    
                    if valid_to_unlock:
                        # Broadcast unlock to everyone
                        await manager.broadcast_to_show(show_id, {
                            "event": "seats_updated",
                            "show_id": show_id,
                            "status": "Available",
                            "seat_ids": valid_to_unlock
                        })

            except json.JSONDecodeError:
                pass
            except Exception as e:
                db.rollback()
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, show_id)
    finally:
        db.close()


# Serve Admin HTML file
@app.get("/admin")
def serve_admin():
    return FileResponse("/frontend/admin.html")


@app.get("/api/admin/vendors", response_model=List[schemas.VendorResponse])
def get_vendors(db: Session = Depends(get_db)):
    return db.query(models.Vendor).order_by(models.Vendor.vendor_id).all()


@app.get("/api/admin/vendors/{vendor_id}/analytics", response_model=schemas.VendorAnalyticsResponse)
def get_vendor_analytics(vendor_id: int, db: Session = Depends(get_db)):
    # Find all venues owned by this vendor
    venues = db.query(models.Venue).filter(models.Venue.vendor_id == vendor_id).all()
    venue_ids = [v.venue_id for v in venues]
    if not venue_ids:
        return {"total_tickets": 0, "total_revenue": Decimal("0.00"), "occupancy_rate": 0.0, "coupon_usage": []}
    
    # Find all shows for these venues
    shows = db.query(models.Show).filter(models.Show.venue_id.in_(venue_ids)).all()
    show_ids = [s.show_id for s in shows]
    if not show_ids:
        return {"total_tickets": 0, "total_revenue": Decimal("0.00"), "occupancy_rate": 0.0, "coupon_usage": []}
    
    # Total show seats
    total_seats_count = db.query(models.ShowSeat).filter(models.ShowSeat.show_id.in_(show_ids)).count()
    
    # Booked seats
    booked_seats = db.query(models.ShowSeat).filter(
        models.ShowSeat.show_id.in_(show_ids),
        models.ShowSeat.status == "Booked"
    ).all()
    
    total_tickets = len(booked_seats)
    total_revenue = sum((s.final_price or Decimal("0.00")) for s in booked_seats)
    
    occupancy_rate = (total_tickets / total_seats_count * 100.0) if total_seats_count > 0 else 0.0
    
    # Coupon usage stats for confirmed bookings
    bookings = db.query(models.Booking).filter(
        models.Booking.show_id.in_(show_ids),
        models.Booking.status == "Confirmed"
    ).all()
    
    coupon_stats = {}
    for b in bookings:
        if b.coupon_id:
            coupon = db.query(models.Coupon).filter(models.Coupon.coupon_id == b.coupon_id).first()
            if coupon:
                # Calculate actual discount: subtotal price of seats in booking minus total_amount paid
                booked_seats_in_booking = db.query(models.ShowSeat).filter(models.ShowSeat.booking_id == b.booking_id).all()
                original_price_sum = sum((s.final_price or Decimal("0.00")) for s in booked_seats_in_booking)
                discount_amount = max(Decimal("0.00"), original_price_sum - b.total_amount)
                
                if coupon.code not in coupon_stats:
                    coupon_stats[coupon.code] = {"count": 0, "total_discount": Decimal("0.00")}
                coupon_stats[coupon.code]["count"] += 1
                coupon_stats[coupon.code]["total_discount"] += discount_amount
                
    coupon_usage = [
        {
            "code": code,
            "count": stats["count"],
            "total_discount": stats["total_discount"]
        } for code, stats in coupon_stats.items()
    ]
    
    return {
        "total_tickets": total_tickets,
        "total_revenue": total_revenue,
        "occupancy_rate": occupancy_rate,
        "coupon_usage": coupon_usage
    }


@app.post("/api/admin/shows", response_model=schemas.ShowResponse)
def create_show(payload: schemas.CreateShowRequest, db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.event_id == payload.event_id).first()
    venue = db.query(models.Venue).filter(models.Venue.venue_id == payload.venue_id).first()
    if not event or not venue:
        raise HTTPException(status_code=404, detail="Event or Venue not found.")
    
    show = models.Show(
        event_id=payload.event_id,
        venue_id=payload.venue_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        base_price=payload.base_price
    )
    db.add(show)
    db.flush()
    
    # Pre-populate show_seats
    seats = db.query(models.Seat).filter(models.Seat.venue_id == show.venue_id).all()
    for seat in seats:
        multiplier = Decimal("1.00")
        if seat.tier_id:
            tier = db.query(models.SeatTier).filter(models.SeatTier.tier_id == seat.tier_id).first()
            if tier:
                multiplier = tier.multiplier
        final_price = show.base_price * multiplier
        
        show_seat = models.ShowSeat(
            show_id=show.show_id,
            seat_id=seat.seat_id,
            booking_id=None,
            final_price=final_price,
            status="Available",
            locked_until=None
        )
        db.add(show_seat)
    db.commit()
    
    return {
        "show_id": show.show_id,
        "event_id": show.event_id,
        "event_title": event.title,
        "event_type": event.event_type,
        "venue_id": show.venue_id,
        "venue_name": venue.name,
        "venue_location": venue.location,
        "start_time": show.start_time,
        "end_time": show.end_time,
        "base_price": show.base_price
    }


@app.post("/api/admin/coupons", response_model=schemas.CouponResponse)
def create_coupon(payload: schemas.CreateCouponRequest, db: Session = Depends(get_db)):
    existing = db.query(models.Coupon).filter(models.Coupon.code == payload.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Coupon code already exists.")
        
    coupon = models.Coupon(
        code=payload.code,
        discount_type=payload.discount_type,
        discount_value=payload.discount_value,
        max_discount=payload.max_discount,
        expiry_date=payload.expiry_date,
        is_active=True
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return coupon


@app.post("/api/admin/seats/override")
async def override_seats(payload: schemas.AdminOverrideRequest, db: Session = Depends(get_db)):
    show_seats = db.query(models.ShowSeat).filter(
        models.ShowSeat.show_id == payload.show_id,
        models.ShowSeat.seat_id.in_(payload.seat_ids)
    ).with_for_update().all()
    
    if len(show_seats) != len(payload.seat_ids):
        raise HTTPException(status_code=400, detail="One or more seats do not exist for this show.")
        
    for ss in show_seats:
        if payload.status == "Booked":
            # Block the seat (simulates manual offline sale)
            ss.status = "Booked"
            ss.booking_id = None
            ss.locked_until = None
        else:
            # Release the seat
            ss.status = "Available"
            ss.booking_id = None
            ss.locked_until = None
            
    db.commit()
    
    # Broadcast the seat update to all active WebSockets connected to this show
    await manager.broadcast_to_show(payload.show_id, {
        "event": "seats_updated",
        "show_id": payload.show_id,
        "status": payload.status,
        "seat_ids": payload.seat_ids
    })
    
    return {"status": "success", "message": f"Successfully updated {len(show_seats)} seats to {payload.status}."}


# Serve static web frontend
@app.get("/")
def serve_index():
    return FileResponse("/frontend/index.html")

# Fallback static mount for CSS, JS, etc.
app.mount("/", StaticFiles(directory="/frontend"), name="frontend")

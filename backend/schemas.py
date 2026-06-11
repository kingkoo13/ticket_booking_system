from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
from decimal import Decimal

# User schemas
class UserBase(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Seat & Tier schemas
class SeatTierResponse(BaseModel):
    tier_id: int
    tier_name: str
    multiplier: Decimal

    class Config:
        from_attributes = True

class SeatResponse(BaseModel):
    seat_id: int
    seat_number: str
    row_num: str
    tier: Optional[SeatTierResponse] = None

    class Config:
        from_attributes = True


# ShowSeat schemas
class ShowSeatResponse(BaseModel):
    show_seat_id: int
    show_id: int
    seat_id: int
    seat_number: str
    row_num: str
    tier_name: Optional[str] = None
    multiplier: Decimal
    final_price: Optional[Decimal] = None
    status: str
    locked_until: Optional[datetime] = None
    locked_by_user_id: Optional[int] = None # We will map booking's user_id or track temporarily

    class Config:
        from_attributes = True


# Event schemas
class EventResponse(BaseModel):
    event_id: int
    title: str
    description: Optional[str] = None
    duration_minutes: int
    genre: Optional[str] = None
    event_type: str

    class Config:
        from_attributes = True


# Show schemas
class ShowResponse(BaseModel):
    show_id: int
    event_id: int
    event_title: str
    event_type: str
    venue_id: int
    venue_name: str
    venue_location: str
    start_time: datetime
    end_time: datetime
    base_price: Decimal

    class Config:
        from_attributes = True


# Coupon schemas
class CouponResponse(BaseModel):
    coupon_id: int
    code: str
    discount_type: str
    discount_value: Decimal
    max_discount: Optional[Decimal] = None
    expiry_date: datetime
    is_active: bool

    class Config:
        from_attributes = True


# Booking schemas
class BookingSeatDetail(BaseModel):
    seat_id: int
    seat_number: str
    row_num: str
    final_price: Decimal

class BookingResponse(BaseModel):
    booking_id: int
    user_id: Optional[int] = None
    show_id: int
    event_title: str
    venue_name: str
    start_time: datetime
    total_amount: Decimal
    status: str
    created_at: datetime
    seats: List[BookingSeatDetail] = []

    class Config:
        from_attributes = True


# Request schemas
class CreateBookingRequest(BaseModel):
    user_id: int
    show_id: int
    seat_ids: List[int]
    coupon_code: Optional[str] = None


class LockSeatsRequest(BaseModel):
    user_id: int
    show_id: int
    seat_ids: List[int]
    lock: bool # True to lock, False to unlock


# Admin & Vendor schemas
class VendorResponse(BaseModel):
    vendor_id: int
    name: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


class CreateShowRequest(BaseModel):
    event_id: int
    venue_id: int
    start_time: datetime
    end_time: datetime
    base_price: Decimal


class CreateCouponRequest(BaseModel):
    code: str
    discount_type: str # 'Flat' or 'Percentage'
    discount_value: Decimal
    max_discount: Optional[Decimal] = None
    expiry_date: datetime


class AdminOverrideRequest(BaseModel):
    show_id: int
    seat_ids: List[int]
    status: str # 'Booked' or 'Available'


class CouponUsageDetail(BaseModel):
    code: str
    count: int
    total_discount: Decimal


class VendorAnalyticsResponse(BaseModel):
    total_tickets: int
    total_revenue: Decimal
    occupancy_rate: float
    coupon_usage: List[CouponUsageDetail] = []


class CreateEventRequest(BaseModel):
    title: str
    description: Optional[str] = None
    duration_minutes: int
    genre: Optional[str] = None
    event_type: str  # 'Movie', 'Concert', 'Stand-up', 'Alternative'


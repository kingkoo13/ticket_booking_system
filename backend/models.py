from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Numeric, Boolean, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    phone = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)

    bookings = relationship("Booking", back_populates="user")


class Vendor(Base):
    __tablename__ = "vendors"

    vendor_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    venues = relationship("Venue", back_populates="vendor")


class Venue(Base):
    __tablename__ = "venues"

    venue_id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.vendor_id", ondelete="SET NULL"), nullable=True)
    name = Column(String(100), nullable=False)
    location = Column(Text, nullable=False)
    capacity = Column(Integer, nullable=False)

    vendor = relationship("Vendor", back_populates="venues")
    tiers = relationship("SeatTier", back_populates="venue", cascade="all, delete-orphan")
    seats = relationship("Seat", back_populates="venue", cascade="all, delete-orphan")
    shows = relationship("Show", back_populates="venue", cascade="all, delete-orphan")


class SeatTier(Base):
    __tablename__ = "seat_tiers"

    tier_id = Column(Integer, primary_key=True, index=True)
    venue_id = Column(Integer, ForeignKey("venues.venue_id", ondelete="CASCADE"), nullable=False)
    tier_name = Column(String(50), nullable=False)
    multiplier = Column(Numeric(3, 2), default=1.00)

    __table_args__ = (
        UniqueConstraint("venue_id", "tier_name", name="uq_venue_tier_name"),
    )

    venue = relationship("Venue", back_populates="tiers")
    seats = relationship("Seat", back_populates="tier")


class Seat(Base):
    __tablename__ = "seats"

    seat_id = Column(Integer, primary_key=True, index=True)
    venue_id = Column(Integer, ForeignKey("venues.venue_id", ondelete="CASCADE"), nullable=False)
    tier_id = Column(Integer, ForeignKey("seat_tiers.tier_id", ondelete="SET NULL"), nullable=True)
    seat_number = Column(String(10), nullable=False)
    row_num = Column(String(5), nullable=False)

    __table_args__ = (
        UniqueConstraint("venue_id", "seat_number", name="uq_venue_seat_number"),
    )

    venue = relationship("Venue", back_populates="seats")
    tier = relationship("SeatTier", back_populates="seats")
    show_seats = relationship("ShowSeat", back_populates="seat", cascade="all, delete-orphan")


class Event(Base):
    __tablename__ = "events"

    event_id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    duration_minutes = Column(Integer, nullable=False)
    genre = Column(String(50))
    event_type = Column(String(50), nullable=False)  # 'Movie', 'Concert', 'Stand-up', 'Other'

    shows = relationship("Show", back_populates="event", cascade="all, delete-orphan")


class Show(Base):
    __tablename__ = "shows"

    show_id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.event_id", ondelete="CASCADE"), nullable=False)
    venue_id = Column(Integer, ForeignKey("venues.venue_id", ondelete="CASCADE"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    base_price = Column(Numeric(10, 2), nullable=False)

    __table_args__ = (
        Index("idx_shows_timeline", "start_time"),
    )

    event = relationship("Event", back_populates="shows")
    venue = relationship("Venue", back_populates="shows")
    show_seats = relationship("ShowSeat", back_populates="show", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="show", cascade="all, delete-orphan")


class Coupon(Base):
    __tablename__ = "coupons"

    coupon_id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    discount_type = Column(String(20), nullable=False)  # 'Flat' or 'Percentage'
    discount_value = Column(Numeric(10, 2), nullable=False)
    max_discount = Column(Numeric(10, 2), nullable=True)
    expiry_date = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)

    bookings = relationship("Booking", back_populates="coupon")


class Booking(Base):
    __tablename__ = "bookings"

    booking_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    show_id = Column(Integer, ForeignKey("shows.show_id", ondelete="CASCADE"), nullable=False)
    coupon_id = Column(Integer, ForeignKey("coupons.coupon_id", ondelete="SET NULL"), nullable=True)
    total_amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), default="Pending")  # Pending, Confirmed, Cancelled, Expired
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="bookings")
    show = relationship("Show", back_populates="bookings")
    coupon = relationship("Coupon", back_populates="bookings")
    show_seats = relationship("ShowSeat", back_populates="booking")


class ShowSeat(Base):
    __tablename__ = "show_seats"

    show_seat_id = Column(Integer, primary_key=True, index=True)
    show_id = Column(Integer, ForeignKey("shows.show_id", ondelete="CASCADE"), nullable=False)
    seat_id = Column(Integer, ForeignKey("seats.seat_id", ondelete="CASCADE"), nullable=False)
    booking_id = Column(Integer, ForeignKey("bookings.booking_id", ondelete="SET NULL"), nullable=True)
    final_price = Column(Numeric(10, 2), nullable=True)
    status = Column(String(20), default="Available")  # Available, Locked, Booked
    locked_until = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("show_id", "seat_id", name="uq_show_seat"),
        Index("idx_show_seats_lookup", "show_id", "status"),
    )

    show = relationship("Show", back_populates="show_seats")
    seat = relationship("Seat", back_populates="show_seats")
    booking = relationship("Booking", back_populates="show_seats")

from datetime import datetime, timedelta
from decimal import Decimal
from database import SessionLocal, Base, engine
import models

def seed_db():
    print("Dropping existing tables...")
    Base.metadata.drop_all(bind=engine)
    
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        print("Seeding users...")
        users = [
            models.User(name="Prashant", email="prashant@example.com", phone="9876543210"),
            models.User(name="Jane Doe", email="jane@example.com", phone="8765432109"),
            models.User(name="John Smith", email="john@example.com", phone="7654321098"),
        ]
        db.add_all(users)
        db.commit()

        print("Seeding vendors...")
        vendors = [
            models.Vendor(name="Metro Cinema Group", email="metro@example.com"),
            models.Vendor(name="Metropolis Promotions", email="metropolis@example.com"),
            models.Vendor(name="Star Comedy Network", email="star@example.com"),
        ]
        db.add_all(vendors)
        db.commit()

        db_vendors = db.query(models.Vendor).all()
        vendor_map = {v.name: v.vendor_id for v in db_vendors}

        print("Seeding coupons...")
        tomorrow = datetime.utcnow() + timedelta(days=5)
        coupons = [
            models.Coupon(code="FLAT50", discount_type="Flat", discount_value=Decimal("50.00"), expiry_date=tomorrow),
            models.Coupon(code="SUPERDEAL", discount_type="Percentage", discount_value=Decimal("20.00"), max_discount=Decimal("100.00"), expiry_date=tomorrow),
            models.Coupon(code="WELCOME10", discount_type="Percentage", discount_value=Decimal("10.00"), expiry_date=tomorrow),
        ]
        db.add_all(coupons)
        db.commit()

        # Define venues, tiers and layout
        venue_configs = [
            {
                "name": "Grand Cinema, Wave Mall",
                "location": "A-Block, City Center",
                "capacity": 50,
                "type": "Movie",
                "vendor": "Metro Cinema Group",
                "tiers": [
                    {"name": "Executive", "multiplier": Decimal("1.00")},
                    {"name": "Premium", "multiplier": Decimal("1.25")},
                    {"name": "Recliner", "multiplier": Decimal("1.50")}
                ],
                "seats": [
                    # A-B: Executive, C-D: Premium, E: Recliner (10 seats per row)
                    {"row": "A", "count": 10, "tier": "Executive"},
                    {"row": "B", "count": 10, "tier": "Executive"},
                    {"row": "C", "count": 10, "tier": "Premium"},
                    {"row": "D", "count": 10, "tier": "Premium"},
                    {"row": "E", "count": 10, "tier": "Recliner"}
                ]
            },
            {
                "name": "Metropolis Arena",
                "location": "Downtown Sports Complex",
                "capacity": 45,
                "type": "Concert",
                "vendor": "Metropolis Promotions",
                "tiers": [
                    {"name": "General Access", "multiplier": Decimal("1.00")},
                    {"name": "Balcony Tier", "multiplier": Decimal("1.30")},
                    {"name": "Front Fan Pit", "multiplier": Decimal("2.00")}
                ],
                "seats": [
                    # Front Fan Pit: row P (10 seats), Balcony: row B (15 seats), General Access: row G (20 seats)
                    {"row": "P", "count": 10, "tier": "Front Fan Pit"},
                    {"row": "B", "count": 15, "tier": "Balcony Tier"},
                    {"row": "G", "count": 20, "tier": "General Access"}
                ]
            },
            {
                "name": "The Comedy Lounge",
                "location": "5th Avenue Broadway",
                "capacity": 28,
                "type": "Stand-up",
                "vendor": "Star Comedy Network",
                "tiers": [
                    {"name": "Standard Capacity", "multiplier": Decimal("1.00")},
                    {"name": "VIP Front Row", "multiplier": Decimal("1.40")}
                ],
                "seats": [
                    # VIP Front: Row V (8 seats), Standard: Row S (20 seats)
                    {"row": "V", "count": 8, "tier": "VIP Front Row"},
                    {"row": "S", "count": 20, "tier": "Standard Capacity"}
                ]
            },
            {
                "name": "Olympia Stadium",
                "location": "Outer Ring Road Sector 4",
                "capacity": 45,
                "type": "Alternative",
                "vendor": "Star Comedy Network",
                "tiers": [
                    {"name": "East Wing Standard", "multiplier": Decimal("1.00")},
                    {"name": "West Wing Premium", "multiplier": Decimal("1.50")},
                    {"name": "VIP Sky Box", "multiplier": Decimal("2.50")}
                ],
                "seats": [
                    # East Wing Standard: E1-E20, West Wing Premium: W1-W20, Sky Box VIP: S1-S5
                    {"row": "E", "count": 20, "tier": "East Wing Standard"},
                    {"row": "W", "count": 20, "tier": "West Wing Premium"},
                    {"row": "S", "count": 5, "tier": "VIP Sky Box"}
                ]
            }
        ]

        print("Seeding venues, tiers, and seats...")
        for config in venue_configs:
            venue = models.Venue(
                vendor_id=vendor_map[config["vendor"]],
                name=config["name"],
                location=config["location"],
                capacity=config["capacity"]
            )
            db.add(venue)
            db.flush() # get venue_id

            # Tiers mapping
            tier_map = {}
            for t_cfg in config["tiers"]:
                tier = models.SeatTier(
                    venue_id=venue.venue_id,
                    tier_name=t_cfg["name"],
                    multiplier=t_cfg["multiplier"]
                )
                db.add(tier)
                db.flush()
                tier_map[t_cfg["name"]] = tier.tier_id
            
            # Seats creation
            for s_cfg in config["seats"]:
                row = s_cfg["row"]
                count = s_cfg["count"]
                tier_name = s_cfg["tier"]
                tier_id = tier_map[tier_name]
                
                for idx in range(1, count + 1):
                    seat_num = f"{row}{idx}"
                    seat = models.Seat(
                        venue_id=venue.venue_id,
                        tier_id=tier_id,
                        seat_number=seat_num,
                        row_num=row
                    )
                    db.add(seat)
            db.commit()

        print("Seeding events...")
        events = [
            models.Event(
                title="Sci-Fi Odyssey: Interstellar Drift",
                description="An epic cinematic journey into the deep cosmos, with breathtaking visuals and score.",
                duration_minutes=150,
                genre="Sci-Fi / Adventure",
                event_type="Movie"
            ),
            models.Event(
                title="Rock Fest 2026: Live & Loud",
                description="Experience the loudest and most energetic rock bands of the decade performing live on stage.",
                duration_minutes=180,
                genre="Rock / Alternative",
                event_type="Concert"
            ),
            models.Event(
                title="Laughter Therapy Night",
                description="Top stand-up comedians sharing hilarious observational comedy and crowd work.",
                duration_minutes=90,
                genre="Comedy / Stand-up",
                event_type="Stand-up"
            ),
            models.Event(
                title="Championship Derby: Super Cup",
                description="The ultimate sporting clash between rival teams for the regional cup trophy.",
                duration_minutes=120,
                genre="Sports / Live Match",
                event_type="Alternative"
            ),
        ]
        db.add_all(events)
        db.commit()

        # Retrieve events and venues to link shows
        db_events = db.query(models.Event).all()
        db_venues = db.query(models.Venue).all()

        event_map = {e.event_type: e.event_id for e in db_events}
        venue_map = {}
        for v in db_venues:
            # simple mapping based on string match
            if "Cinema" in v.name:
                venue_map["Movie"] = v
            elif "Arena" in v.name:
                venue_map["Concert"] = v
            elif "Lounge" in v.name:
                venue_map["Stand-up"] = v
            else:
                venue_map["Alternative"] = v

        print("Seeding shows and pre-populating show_seats...")
        # We will create shows for today
        now = datetime.utcnow()
        shows = [
            models.Show(
                event_id=event_map["Movie"],
                venue_id=venue_map["Movie"].venue_id,
                start_time=now + timedelta(hours=2),
                end_time=now + timedelta(hours=4.5),
                base_price=Decimal("200.00")
            ),
            models.Show(
                event_id=event_map["Concert"],
                venue_id=venue_map["Concert"].venue_id,
                start_time=now + timedelta(hours=4),
                end_time=now + timedelta(hours=7),
                base_price=Decimal("500.00")
            ),
            models.Show(
                event_id=event_map["Stand-up"],
                venue_id=venue_map["Stand-up"].venue_id,
                start_time=now + timedelta(hours=1),
                end_time=now + timedelta(hours=2.5),
                base_price=Decimal("300.00")
            ),
            models.Show(
                event_id=event_map["Alternative"],
                venue_id=venue_map["Alternative"].venue_id,
                start_time=now + timedelta(hours=3),
                end_time=now + timedelta(hours=5),
                base_price=Decimal("150.00")
            ),
        ]
        db.add_all(shows)
        db.commit()

        # Seed show_seats for each show
        db_shows = db.query(models.Show).all()
        for show in db_shows:
            # Get seats for this show's venue
            seats = db.query(models.Seat).filter(models.Seat.venue_id == show.venue_id).all()
            for seat in seats:
                # Calculate initial final_price = show.base_price * tier.multiplier
                multiplier = Decimal("1.00")
                if seat.tier:
                    multiplier = seat.tier.multiplier
                
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
        print("Database seeded successfully with all typologies!")
        
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()

# OFFICIAL DEVELOPMENT BLUEPRINT: REAL-TIME TICKET BOOKING SYSTEM
Target Environment: macOS (Apple Silicon/Intel) via Docker Desktop & Python 3.11+
Database Engine: PostgreSQL 18+ (Isolated Container Mode)

---

## 1. CORE SYSTEM ARCHITECTURE

A high-traffic booking ecosystem splits data streams into two channels: an asynchronous, bidirectional channel for zero-latency screen layout synchronization, and a strict ACID-compliant transactional channel for final ticketing settlement.

### System Topography & Data Flows


1. Real-Time View State Channel:
   * [cite_start]Clients open persistent WebSockets connections to broadcast active selection metrics[cite: 363].
   * [cite_start]State transitions ("Available" ↔ "Locked") are instantly synchronized across all connected client interfaces[cite: 360, 361].

2. Transactional Isolation Channel:
   * [cite_start]System actions requiring state permanence use isolated relational transactions with row-level read blocks[cite: 4, 365].
   * [cite_start]Outbound operations to third-party providers use state validation loops before updating records[cite: 343].

---

## 2. MODULAR PRICING ENGINE ARCHITECTURE

[cite_start]To reconcile varying spatial properties (e.g., rigid theater seating grids vs. boundaryless general admission fields), ticket validation is managed using an algorithmic pricing calculation layer instead of data attributes[cite: 326, 328].

### System Pricing Equation
[cite_start]The system calculates ticket valuation at execution using the following logic[cite: 329]:

$$\text{Final Ticket Price} = (\text{Show Base Price} \times \text{Tier Multiplier}) - \text{Discount Applied}$$

### Segment Strategy Matrix

| Booking Domain | Layout Typology | Pricing Implementation |
| :--- | :--- | :--- |
| **1. [cite_start]Movie Cinema** [cite: 332] | [cite_start]Defined Matrix Configuration (Rows/Columns) [cite: 332] | [cite_start]**Tiered Modifiers:** Premium seats execute standard scaling (e.g., Recliners = $1.5\times$)[cite: 333]. |
| **2. [cite_start]Live Concert** [cite: 334] | [cite_start]Hybrid Spatial Polygons (Reserved Blocks + Open General Access) [cite: 334] | [cite_start]**Zonal Modifiers:** High-demand spaces scale globally (e.g., Front Pit = $2.0\times$)[cite: 335]. |
| **3. [cite_start]Stand-up Comedy** [cite: 336] | [cite_start]Unreserved Club Formats / Dense Micro-seating [cite: 336] | [cite_start]**Flat / Segmented:** Low entry price floors relying on immediate inventory capacity[cite: 337]. |
| **4. [cite_start]Alternative Venues** [cite: 338] | [cite_start]Scaled Multi-tier Sectors (Stadium Stand Sectors) [cite: 338] | [cite_start]**Complex Structuring:** Heavy structural scaling driven by block metrics[cite: 339]. |

---

## 3. RELATIONAL DATABASE SPECIFICATION (DDL)

[cite_start]Execute this script inside your local connection client to drop existing entities and establish the expanded multi-tier tracking structures[cite: 10, 368, 369].

```sql
-- Clean active schemas
DROP TABLE IF EXISTS show_seats CASCADE;
DROP TABLE IF EXISTS bookings CASCADE;
DROP TABLE IF EXISTS coupons CASCADE;
DROP TABLE IF EXISTS shows CASCADE;
DROP TABLE IF EXISTS events CASCADE;
DROP TABLE IF EXISTS seats CASCADE;
DROP TABLE IF EXISTS seat_tiers CASCADE;
DROP TABLE IF EXISTS venues CASCADE;
DROP TABLE IF EXISTS vendors CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- 1. System Users Account Tracking
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 1b. Vendors Account Tracking
CREATE TABLE vendors (
    vendor_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Location Venues Structural Record
CREATE TABLE venues (
    venue_id SERIAL PRIMARY KEY,
    vendor_id INT REFERENCES vendors(vendor_id) ON DELETE SET NULL,
    name VARCHAR(100) NOT NULL,
    location TEXT NOT NULL,
    capacity INT NOT NULL
);

-- 3. Area Modifiers (Pricing Multipliers per Zone)
CREATE TABLE seat_tiers (
    tier_id SERIAL PRIMARY KEY,
    venue_id INT REFERENCES venues(venue_id) ON DELETE CASCADE,
    tier_name VARCHAR(50) NOT NULL, -- e.g., 'Recliner', 'Fan Pit', 'Executive'
    multiplier DECIMAL(3, 2) DEFAULT 1.00, -- e.g., 1.50, 2.00
    UNIQUE(venue_id, tier_name)
);

-- 4. Unique Inventory Elements
CREATE TABLE seats (
    seat_id SERIAL PRIMARY KEY,
    venue_id INT REFERENCES venues(venue_id) ON DELETE CASCADE,
    tier_id INT REFERENCES seat_tiers(tier_id) ON DELETE SET NULL,
    seat_number VARCHAR(10) NOT NULL,
    row_num VARCHAR(5) NOT NULL,
    UNIQUE (venue_id, seat_number)
);

-- 5. Show Content Assets
CREATE TABLE events (
    event_id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    duration_minutes INT NOT NULL,
    genre VARCHAR(50),
    event_type VARCHAR(50) NOT NULL -- 'Movie', 'Concert', 'Stand-up', 'Other'
);

-- 6. Individual Timeline Assignments
CREATE TABLE shows (
    show_id SERIAL PRIMARY KEY,
    event_id INT REFERENCES events(event_id) ON DELETE CASCADE,
    venue_id INT REFERENCES venues(venue_id) ON DELETE CASCADE,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    base_price DECIMAL(10, 2) NOT NULL -- Base temporal price point
);

-- 7. Campaign Ledger (Discount Vouchers)
CREATE TABLE coupons (
    coupon_id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    discount_type VARCHAR(20) NOT NULL, -- 'Flat' or 'Percentage'
    discount_value DECIMAL(10, 2) NOT NULL,
    max_discount DECIMAL(10, 2), -- Cap value limit for percentage deductions
    expiry_date TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

-- 8. Final Invoices Transactions Header
CREATE TABLE bookings (
    booking_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id) ON DELETE SET NULL,
    show_id INT REFERENCES shows(show_id) ON DELETE CASCADE,
    coupon_id INT REFERENCES coupons(coupon_id) ON DELETE SET NULL,
    total_amount DECIMAL(10, 2) NOT NULL, -- Final net charge
    status VARCHAR(20) DEFAULT 'Pending', -- Pending, Confirmed, Cancelled, Expired
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. Real-Time Dynamic State Ledger (Inventory Concurrency Controls)
CREATE TABLE show_seats (
    show_seat_id SERIAL PRIMARY KEY,
    show_id INT REFERENCES shows(show_id) ON DELETE CASCADE,
    seat_id INT REFERENCES seats(seat_id) ON DELETE CASCADE,
    booking_id INT REFERENCES bookings(booking_id) ON DELETE SET NULL,
    final_price DECIMAL(10, 2), -- Computed value captured at lock timestamp
    status VARCHAR(20) DEFAULT 'Available', -- Available, Locked, Booked
    locked_until TIMESTAMP, -- Cache eviction reference point
    UNIQUE (show_id, seat_id)
);

-- Optimization indexing arrays for production scaling
CREATE INDEX idx_show_seats_lookup ON show_seats(show_id, status);
CREATE INDEX idx_shows_timeline ON shows(start_time);

---

## 4. VENDOR ADMIN PANEL SPECIFICATION

The vendor administration panel enables management of venues, scheduling, coupons, and live occupancy tracking.

### Core Features

1. **Vendor Switching & Isolation**:
   * Switch between simulated vendors to filter venues, shows, and revenue.
2. **Dynamic Live Analytics**:
   * Displays gross revenue, seats filled percentage (occupancy rate), and ticket counts.
   * Highlights coupon code metrics.
3. **Show Scheduler**:
   * Vendors can create new show timings and assign base ticket prices.
4. **Coupon Campaigns**:
   * Vendors/admins can create and configure active coupon codes.
5. **Interactive Booking Override**:
   * Live seating layout showing real-time locks and bookings.
   * Ability to click available seats and manually block them (representing offline or VIP sales) or unlock manually held seats.
# Real-Time Ticket Booking System (BookMyShow Clone)

A high-performance, real-time ticket booking ecosystem mimicking the iconic **BookMyShow** user experience. The application separates data streams into a zero-latency WebSocket synchronization channel for active seat locks, and an ACID-compliant transactional channel utilizing PostgreSQL row-level locks for final ticket purchases.

---

## 🚀 Key Features

### 1. Customer Seating Layouts
- **Movie Cinema**: Defined grid matrix layout (e.g. Rows/Columns) featuring tiered modifiers (e.g., Recliners scaling base price by $1.5\times$).
- **Live Concert**: Hybrid spatial layouts with reserved balcony tiers, general access sections, and a premium front fan pit ($2.0\times$ multiplier).
- **Stand-up Comedy**: Unreserved club formats and VIP front rows.
- **Alternative Venues**: Large stadium sectors (East/West wings and VIP Sky Boxes).

### 2. Zero-Latency State Sync (WebSockets)
- Active user clicks trigger 60-second temporary seat locks broadcasted in real-time.
- Other connected users instantly see held seats turn orange with a lock icon.

### 3. Double-Booking Prevention (ACID Transactions)
- Final settlements execute database transactions using `SELECT ... FOR UPDATE` row-level locks on the selected seat rows.
- Blocks concurrent users attempting to purchase the same seat, even under high-traffic simultaneous requests.

### 4. Vendor Command Center
- Switch simulated vendor accounts to filter statistics.
- **Live Analytics**: Real-time sales telemetry showing gross revenue, ticket counts, and capacity occupancy percentages.
- **Interactive Seat Overrides**: Live seat grid allowing vendors to click seats to manually block them (for VIP or offline sales) or release them.
- **Show Scheduler**: Setup new events, assign venues, and schedule time slots.
- **Campaign Coupon Manager**: Launch percentage-based or flat discount promotional coupons.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy, Uvicorn, Psycopg2.
- **Database**: PostgreSQL 18+ (Isolated Container Mode).
- **Frontend**: Vanilla HTML5, CSS3 (BookMyShow Dark/Light Theme), Javascript.
- **Infrastructure**: Docker & Docker Compose.

---

## 📦 Getting Started

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.

### Installation & Execution
1. Clone the repository and navigate to the project directory:
   ```bash
   git clone https://github.com/kingkoo13/ticket_booking_system.git
   cd ticket_booking_system
   ```

2. Spin up the Docker containers:
   ```bash
   docker compose up --build -d
   ```

3. Access the interfaces:
   - 🎟️ **Customer Booking Page**: [http://localhost:8000](http://localhost:8000)
   - 📊 **Vendor Command Center**: [http://localhost:8000/admin](http://localhost:8000/admin)

4. **Initialize/Reset Database**:
   - Click the **Reset DB** button on either frontend page header, which executes the seeding logic to reset all schemas and preload mock users, shows, and coupons.

---

## 🧪 Verification & Integration Tests

The project includes test scripts to verify transactional integrity and administrative APIs.

### 1. Concurrency Check (`verify_booking.py`)
Simulates two concurrent users attempting to buy the exact same seat at the same millisecond.
```bash
python3 verify_booking.py
```
*Expected result: One succeeds and locks the booking; the other is safely rejected with status 400 (Seat already booked).*

### 2. Admin API Verification (`test_admin.py`)
Tests show scheduling, admin manual seat blocks, double booking rejection on blocked seats, and analytics.
```bash
python3 test_admin.py
```

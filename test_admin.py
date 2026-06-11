import urllib.request
import urllib.error
import json
import time

BASE_URL = "http://localhost:8000"

def get_json(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())

def post_json(url, payload):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json'},
        method="POST"
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())

def run_admin_test():
    print("1. Fetching list of vendors...")
    vendors = get_json(f"{BASE_URL}/api/admin/vendors")
    print(f"Found {len(vendors)} vendors: {[v['name'] for v in vendors]}")
    assert len(vendors) == 3, "Expected 3 seeded vendors."
    
    metro_vendor_id = vendors[0]["vendor_id"]
    
    print("\n2. Scheduling a new show (Movie at Metro Cinema)...")
    # Date formatting
    now_ts = time.time()
    start_time = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(now_ts + 7200))
    end_time = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(now_ts + 18000))
    
    # event_id=1 (Sci-Fi Movie), venue_id=1 (Grand Cinema, owned by vendor 1)
    show_payload = {
        "event_id": 1,
        "venue_id": 1,
        "start_time": start_time,
        "end_time": end_time,
        "base_price": "250.00"
    }
    
    show = post_json(f"{BASE_URL}/api/admin/shows", show_payload)
    new_show_id = show["show_id"]
    print(f"Scheduled show successfully! Show ID: {new_show_id}, Base Price: {show['base_price']}")
    
    print("\n3. Verifying show_seats are populated for the new show...")
    seats = get_json(f"{BASE_URL}/api/shows/{new_show_id}/seats")
    print(f"Seeded {len(seats)} seats for Show {new_show_id}.")
    assert len(seats) == 50, "Expected 50 seat entries."
    
    # Let's override seat ID 3 to be blocked by admin
    # In venue 1, seat_id 3 is typically row A seat A3
    target_seat_id = 3
    print(f"\n4. Manually blocking Seat ID {target_seat_id} (Admin Override)...")
    override_payload = {
        "show_id": new_show_id,
        "seat_ids": [target_seat_id],
        "status": "Booked"
    }
    override_res = post_json(f"{BASE_URL}/api/admin/seats/override", override_payload)
    print("Override Response:", override_res["message"])
    
    print("\n5. Confirming blocked seat is marked as Booked in seats API...")
    seats = get_json(f"{BASE_URL}/api/shows/{new_show_id}/seats")
    target_seat = next(s for s in seats if s["seat_id"] == target_seat_id)
    print(f"Seat ID {target_seat_id} status: {target_seat['status']}")
    assert target_seat["status"] == "Booked", "Expected seat status to be Booked."
    
    print("\n6. Attempting standard customer booking on the blocked seat...")
    booking_payload = {
        "user_id": 1,
        "show_id": new_show_id,
        "seat_ids": [target_seat_id],
        "coupon_code": None
    }
    try:
        post_json(f"{BASE_URL}/api/bookings", booking_payload)
        print("FAIL: Double booking was allowed on blocked seat!")
    except urllib.error.HTTPError as e:
        error_details = json.loads(e.read().decode())["detail"]
        print(f"SUCCESS: Booking rejected with status {e.code}. Details: {error_details}")
        assert e.code == 400, f"Expected status 400, got {e.code}"
        assert "already booked" in error_details.lower(), "Expected seat to be flagged as already booked."
        
    print("\n7. Fetching vendor analytics and verifying metrics...")
    analytics = get_json(f"{BASE_URL}/api/admin/vendors/{metro_vendor_id}/analytics")
    print("Metro Vendor Analytics:", json.dumps(analytics, indent=2))
    # Note: verify_booking booked seat ID 1 on show ID 1 (which belongs to Metro Cinema venue 1).
    # Plus we manually blocked seat ID 3 on show ID 5. Both belong to Metro Cinema.
    # Total tickets sold should be at least 2
    print(f"Total tickets sold: {analytics['total_tickets']}")
    assert analytics["total_tickets"] >= 2, "Expected at least 2 booked tickets."
    
    print("\nADMIN INTEGRATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_admin_test()

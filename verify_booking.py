import urllib.request
import urllib.error
import json
import threading
import time

BASE_URL = "http://localhost:8000"

def reset_db():
    print("Resetting database...")
    req = urllib.request.Request(f"{BASE_URL}/api/db/reset", method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode())
            print("DB Reset Response:", res_data.get("message"))
    except Exception as e:
        print("Failed to reset DB:", e)


def book_seat(user_id, show_id, seat_ids, results, thread_id):
    payload = {
        "user_id": user_id,
        "show_id": show_id,
        "seat_ids": seat_ids,
        "coupon_code": None
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        f"{BASE_URL}/api/bookings",
        data=data,
        headers={'Content-Type': 'application/json'},
        method="POST"
    )
    
    # Wait for sync signal
    time.sleep(0.1) 
    
    try:
        start_time = time.time()
        with urllib.request.urlopen(req) as response:
            elapsed = time.time() - start_time
            res_data = json.loads(response.read().decode())
            results.append({
                "thread_id": thread_id,
                "status": "SUCCESS",
                "code": response.status,
                "elapsed": elapsed,
                "booking_id": res_data.get("booking_id")
            })
    except urllib.error.HTTPError as e:
        elapsed = time.time() - start_time
        try:
            error_detail = json.loads(e.read().decode()).get("detail", str(e))
        except:
            error_detail = str(e)
        results.append({
            "thread_id": thread_id,
            "status": "FAILED",
            "code": e.code,
            "elapsed": elapsed,
            "error": error_detail
        })
    except Exception as e:
        results.append({
            "thread_id": thread_id,
            "status": "ERROR",
            "error": str(e)
        })


def run_concurrency_test():
    # 1. Reset DB
    reset_db()
    
    # We want to book show_id = 1, seat_id = 1 (usually seat A1 in Cinema)
    show_id = 1
    seat_ids = [1]
    
    results = []
    
    # Create threads representing two concurrent users
    t1 = threading.Thread(target=book_seat, args=(1, show_id, seat_ids, results, "User_1"))
    t2 = threading.Thread(target=book_seat, args=(2, show_id, seat_ids, results, "User_2"))
    
    print("\nLaunching simultaneous booking requests for Seat ID 1...")
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
    
    print("\n--- TEST RESULTS ---")
    successes = 0
    failures = 0
    
    for res in results:
        if res["status"] == "SUCCESS":
            successes += 1
            print(f"[{res['thread_id']}] SUCCESS - Booked! Booking ID: {res['booking_id']} (Time: {res['elapsed']:.3f}s)")
        else:
            failures += 1
            print(f"[{res['thread_id']}] FAILED - status code: {res['code']}, details: {res['error']} (Time: {res['elapsed']:.3f}s)")
            
    print("--------------------")
    if successes == 1 and failures == 1:
        print("VERIFICATION PASSED: Double booking was successfully prevented by transaction row locks.")
    else:
        print("VERIFICATION FAILED: Unexpected distribution of successes/failures.")

if __name__ == "__main__":
    # Wait a second before execution in case server is just booting
    time.sleep(1)
    run_concurrency_test()

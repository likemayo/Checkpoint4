"""
Availability and Failure Testing Script

Scenarios:
1. Circuit breaker functionality - system recovers from payment failures
2. Rate limiting - system gracefully handles overload

Tests verify the system satisfies availability quality attributes.
"""

import requests
import time
from datetime import datetime


class AvailabilityTester:
    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        
    def test_circuit_breaker(self):
        """
        Test Scenario: Payment service failures trigger circuit breaker
        Expected behavior:
        1. First 3 failures pass through
        2. Circuit opens after 3 failures
        3. Subsequent requests fail fast (circuit open)
        4. After timeout, circuit moves to half-open
        5. Successful request closes circuit
        """
        print("\n" + "="*60)
        print("Circuit Breaker Test")
        print("="*60)
        print("Testing payment failure handling and recovery...")
        print()
        
        checkout_url = f"{self.base_url}/checkout"
        
        # Phase 1: Trigger failures to open circuit
        print("Phase 1: Triggering failures to open circuit")
        print("-" * 60)
        
        failure_data = {
            "payment_method": "DECLINE_TEST",
            "amount_cents": 1000
        }
        
        for i in range(1, 5):
            try:
                start = time.time()
                response = requests.post(checkout_url, json=failure_data, timeout=5)
                duration = time.time() - start
                
                print(f"Request {i}:")
                print(f"  Status: {response.status_code}")
                print(f"  Duration: {duration*1000:.0f}ms")
                
                if response.status_code == 503:
                    print(f"  ✓ Circuit OPEN - Failing fast!")
                elif response.status_code == 400:
                    print(f"  Payment declined (circuit still closed)")
                else:
                    print(f"  Response: {response.json()}")
                
                print()
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Request {i} error: {e}\n")
        
        # Phase 2: Wait for recovery timeout
        print("\nPhase 2: Waiting for circuit breaker recovery timeout (30s)...")
        print("-" * 60)
        for remaining in range(30, 0, -5):
            print(f"  ⏳ {remaining} seconds remaining...")
            time.sleep(5)
        
        print("\n Phase 3: Testing recovery with successful payment")
        print("-" * 60)
        
        success_data = {
            "payment_method": "CREDIT_CARD",
            "amount_cents": 1000
        }
        
        try:
            start = time.time()
            response = requests.post(checkout_url, json=success_data, timeout=5)
            duration = time.time() - start
            
            print(f"Recovery Request:")
            print(f"  Status: {response.status_code}")
            print(f"  Duration: {duration*1000:.0f}ms")
            
            if response.status_code == 200:
                print(f"  ✓ Circuit CLOSED - System recovered!")
            else:
                print(f"  Response: {response.json()}")
                
        except Exception as e:
            print(f"Recovery request error: {e}")
        
        print("\n" + "="*60)
        print("Circuit Breaker Test Complete")
        print("="*60 + "\n")
    
    def test_rate_limiting(self):
        """
        Test Scenario: Rate limiting protects system from overload
        Expected behavior:
        1. First 5 requests succeed (within rate limit)
        2. 6th+ requests are rejected with 429 status
        3. After window expires, requests succeed again
        """
        print("\n" + "="*60)
        print("Rate Limiting Test")
        print("="*60)
        print("Testing traffic overload protection...")
        print()
        
        test_url = f"{self.base_url}/checkout"  # Or any rate-limited endpoint
        
        print("Phase 1: Testing rate limit boundary (5 req/min)")
        print("-" * 60)
        
        test_data = {"payment_method": "CREDIT_CARD", "amount_cents": 100}
        
        results = {
            'allowed': 0,
            'blocked': 0
        }
        
        # Send 10 requests rapidly
        for i in range(1, 11):
            try:
                response = requests.post(test_url, json=test_data, timeout=5)
                
                if response.status_code == 429:
                    results['blocked'] += 1
                    print(f"Request {i:2d}: ⛔ BLOCKED (Rate limit exceeded)")
                else:
                    results['allowed'] += 1
                    print(f"Request {i:2d}: ✓ ALLOWED (Status: {response.status_code})")
                
                time.sleep(0.2)  # Small delay between requests
                
            except Exception as e:
                print(f"Request {i:2d}: ❌ ERROR - {e}")
        
        print()
        print("Results:")
        print(f"  Allowed: {results['allowed']}")
        print(f"  Blocked: {results['blocked']}")
        
        if results['blocked'] > 0:
            print(f"  ✓ Rate limiting is ACTIVE and protecting the system")
        else:
            print(f"  ⚠ Rate limiting may not be configured correctly")
        
        print("\n" + "="*60)
        print("Rate Limiting Test Complete")
        print("="*60 + "\n")
    
    def test_system_availability(self):
        """
        Test overall system availability by checking health endpoint.
        """
        print("\n" + "="*60)
        print("System Availability Test")
        print("="*60)
        
        health_url = f"{self.base_url}/monitoring/api/health"
        
        try:
            response = requests.get(health_url, timeout=5)
            data = response.json()
            
            print(f"System Status: {data.get('status', 'unknown').upper()}")
            print(f"Uptime: {data.get('uptime_seconds', 0):.2f} seconds")
            print(f"Error Rate: {data.get('error_rate_per_second', 0):.4f} errors/sec")
            
            if data.get('status') == 'healthy':
                print("✓ System is HEALTHY and available")
            else:
                print("⚠ System is in DEGRADED state")
                
        except Exception as e:
            print(f"❌ System health check failed: {e}")
        
        print("="*60 + "\n")


def run_all_availability_tests():
    """Run all availability and reliability tests."""
    print("\n" + "="*70)
    print(" " * 15 + "AVAILABILITY & RELIABILITY TEST SUITE")
    print("="*70)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    tester = AvailabilityTester()
    
    # Test 1: System availability
    tester.test_system_availability()
    
    time.sleep(2)
    
    # Test 2: Circuit breaker
    tester.test_circuit_breaker()
    
    time.sleep(2)
    
    # Test 3: Rate limiting
    tester.test_rate_limiting()
    
    print("\n" + "="*70)
    print(" " * 20 + "ALL TESTS COMPLETE")
    print("="*70)
    print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")


if __name__ == "__main__":
    print("\n🔍 Starting Availability & Reliability Tests...")
    print("Make sure the application is running on http://localhost:5000\n")
    
    input("Press Enter to start tests...")
    
    run_all_availability_tests()
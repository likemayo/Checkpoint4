"""
Load Testing Script for Performance Scenario Verification

Scenario: High traffic during flash sales
Expected: System maintains response time under 2 seconds for 95% of requests
"""

import requests
import time
import statistics
import concurrent.futures
from datetime import datetime
import json


class LoadTester:
    def __init__(self, base_url="http://localhost:5000", num_requests=100, concurrent_users=10):
        self.base_url = base_url
        self.num_requests = num_requests
        self.concurrent_users = concurrent_users
        self.response_times = []
        self.errors = []
        self.successful_requests = 0
        
    def single_request(self, endpoint="/"):
        """Make a single request and record metrics."""
        start_time = time.time()
        
        try:
            response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
            duration = time.time() - start_time
            
            self.response_times.append(duration)
            
            if response.status_code == 200:
                self.successful_requests += 1
                return {'success': True, 'duration': duration, 'status': response.status_code}
            else:
                self.errors.append(f"HTTP {response.status_code}")
                return {'success': False, 'duration': duration, 'status': response.status_code}
                
        except Exception as e:
            duration = time.time() - start_time
            self.errors.append(str(e))
            return {'success': False, 'duration': duration, 'error': str(e)}
    
    def run_load_test(self, endpoint="/"):
        """Run load test with concurrent users."""
        print(f"\n{'='*60}")
        print(f"Load Test Starting")
        print(f"{'='*60}")
        print(f"Target: {self.base_url}{endpoint}")
        print(f"Total Requests: {self.num_requests}")
        print(f"Concurrent Users: {self.concurrent_users}")
        print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        start = time.time()
        
        # Use ThreadPoolExecutor for concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrent_users) as executor:
            futures = [executor.submit(self.single_request, endpoint) for _ in range(self.num_requests)]
            
            # Wait for all requests to complete
            completed = 0
            for future in concurrent.futures.as_completed(futures):
                completed += 1
                if completed % 10 == 0:
                    print(f"Progress: {completed}/{self.num_requests} requests completed")
        
        total_duration = time.time() - start
        
        # Calculate statistics
        self.print_results(total_duration)
        
    def print_results(self, total_duration):
        """Print test results and statistics."""
        print(f"\n{'='*60}")
        print(f"Load Test Results")
        print(f"{'='*60}")
        
        if not self.response_times:
            print("No successful requests!")
            return
        
        # Calculate percentiles
        sorted_times = sorted(self.response_times)
        p50 = sorted_times[int(len(sorted_times) * 0.50)] if sorted_times else 0
        p95 = sorted_times[int(len(sorted_times) * 0.95)] if sorted_times else 0
        p99 = sorted_times[int(len(sorted_times) * 0.99)] if sorted_times else 0
        
        # Success rate
        success_rate = (self.successful_requests / self.num_requests) * 100
        
        # Requests per second
        rps = self.num_requests / total_duration if total_duration > 0 else 0
        
        print(f"\n📊 Performance Metrics:")
        print(f"  Total Requests:        {self.num_requests}")
        print(f"  Successful Requests:   {self.successful_requests}")
        print(f"  Failed Requests:       {len(self.errors)}")
        print(f"  Success Rate:          {success_rate:.2f}%")
        print(f"  Total Duration:        {total_duration:.2f}s")
        print(f"  Requests/Second:       {rps:.2f}")
        
        print(f"\n⏱️  Response Times:")
        print(f"  Average:               {statistics.mean(self.response_times)*1000:.2f}ms")
        print(f"  Median (P50):          {p50*1000:.2f}ms")
        print(f"  95th Percentile (P95): {p95*1000:.2f}ms")
        print(f"  99th Percentile (P99): {p99*1000:.2f}ms")
        print(f"  Min:                   {min(self.response_times)*1000:.2f}ms")
        print(f"  Max:                   {max(self.response_times)*1000:.2f}ms")
        
        # Scenario verification
        print(f"\n✅ Scenario Verification:")
        if p95 < 2.0:  # 2 seconds
            print(f"  ✓ PASSED: P95 response time ({p95*1000:.0f}ms) is under 2000ms")
        else:
            print(f"  ✗ FAILED: P95 response time ({p95*1000:.0f}ms) exceeds 2000ms")
        
        if success_rate >= 99.0:
            print(f"  ✓ PASSED: Success rate ({success_rate:.2f}%) meets 99% SLO")
        else:
            print(f"  ✗ FAILED: Success rate ({success_rate:.2f}%) below 99% SLO")
        
        if self.errors:
            print(f"\n❌ Errors ({len(self.errors)} total):")
            error_counts = {}
            for error in self.errors:
                error_counts[error] = error_counts.get(error, 0) + 1
            for error, count in error_counts.items():
                print(f"  - {error}: {count} occurrences")
        
        print(f"\n{'='*60}\n")


def run_flash_sale_load_test():
    """Test flash sale endpoints under load."""
    print("🔥 Flash Sale Performance Test")
    
    tester = LoadTester(
        base_url="http://localhost:5000",
        num_requests=200,
        concurrent_users=20
    )
    
    tester.run_load_test("/flash/products")


def run_checkout_load_test():
    """Test checkout endpoint under load."""
    print("🛒 Checkout Performance Test")
    
    tester = LoadTester(
        base_url="http://localhost:5000",
        num_requests=100,
        concurrent_users=10
    )
    
    tester.run_load_test("/checkout")


def run_all_tests():
    """Run all load tests."""
    print("\n" + "="*60)
    print("LOAD TESTING SUITE")
    print("="*60)
    
    # Test 1: Flash sale page load
    run_flash_sale_load_test()
    
    time.sleep(2)  # Brief pause between tests
    
    # Test 2: Checkout performance
    # run_checkout_load_test()  # Uncomment when checkout is ready


if __name__ == "__main__":
    run_all_tests()
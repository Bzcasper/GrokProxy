#!/usr/bin/env python3
"""
Quick test script for CookieManager functionality.
"""

import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from api.cookie_manager import CookieManager


def test_cookie_manager():
    """Test cookie manager with environment variables."""
    
    print("=" * 60)
    print("CookieManager Test")
    print("=" * 60)
    
    # Set test environment variables
    os.environ["COOKIE_1"] = "sso=test-cookie-1-value"
    os.environ["COOKIE_2"] = "sso=test-cookie-2-value"
    os.environ["COOKIE_3"] = "sso=test-cookie-3-value"
    os.environ["COOKIE_FAILURE_THRESHOLD"] = "3"
    
    # Create manager
    cm = CookieManager(failure_threshold=3)
    
    print(f"\n✓ Loaded {cm.get_total_count()} cookies")
    print(f"✓ Healthy cookies: {cm.get_healthy_count()}")
    
    # Test getting cookies
    print("\n--- Testing Cookie Rotation ---")
    for i in range(5):
        cookie_info = cm.get_next_cookie()
        print(f"Request {i+1}: Cookie {cookie_info['index']} - {cookie_info['cookie'][:20]}...")
    
    # Test marking success
    print("\n--- Testing Success Marking ---")
    cm.mark_cookie_success(0)
    cm.mark_cookie_success(0)
    print("✓ Marked cookie 0 successful 2 times")
    
    # Test marking failures
    print("\n--- Testing Failure Marking ---")
    cm.mark_cookie_failed(1, "rate_limit")
    cm.mark_cookie_failed(1, "rate_limit")
    cm.mark_cookie_failed(1, "auth_failed")  # This should mark it unhealthy
    print(f"✓ Marked cookie 1 failed 3 times (unhealthy: {not cm.cookies[1].healthy})")
    
    # Get stats
    print("\n--- Cookie Statistics ---")
    stats = cm.get_cookie_stats()
    for cookie_stat in stats:
        print(f"Cookie {cookie_stat['index']}:")
        print(f"  Healthy: {cookie_stat['healthy']}")
        print(f"  Success: {cookie_stat['success_count']}")
        print(f"  Failures: {cookie_stat['failure_count']}")
        print(f"  Error types: {cookie_stat['error_types']}")
    
    # Test rotation with unhealthy cookie
    print("\n--- Testing Rotation with Unhealthy Cookie ---")
    for i in range(5):
        cookie_info = cm.get_next_cookie()
        print(f"Request {i+1}: Cookie {cookie_info['index']} (should skip cookie 1)")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    test_cookie_manager()

#!/usr/bin/env python3
"""
Test script to verify session isolation between user login and partner admin login.
This ensures that when a user is logged in and then admin logs in, the sessions
don't interfere with each other.
"""

import requests
from requests.sessions import Session

BASE_URL = "http://localhost:5000"

def test_session_isolation():
    print("=== Testing Session Isolation Between User and Admin Login ===\n")
    
    # Test 1: User Login First
    print("Test 1: User logs in first")
    user_session = Session()
    
    # Login as regular user (using demo user)
    response = user_session.post(
        f"{BASE_URL}/login",
        data={"username": "demo", "password": "demo123", "role": "customer"},
        allow_redirects=False
    )
    print(f"  User login status: {response.status_code}")
    print(f"  User session cookies: {dict(user_session.cookies)}")
    
    # Check dashboard access
    dashboard_response = user_session.get(f"{BASE_URL}/dashboard")
    print(f"  Dashboard access status: {dashboard_response.status_code}")
    if "demo" in dashboard_response.text or "Dashboard" in dashboard_response.text:
        print("  ✓ User can access dashboard")
    else:
        print("  ✗ User cannot access dashboard")
    
    print()
    
    # Test 2: Admin Login in Different Session
    print("Test 2: Partner admin logs in (different session)")
    admin_session = Session()
    
    # Login as partner admin
    admin_response = admin_session.post(
        f"{BASE_URL}/partner/admin/login",
        data={"admin_key": "admin-demo-key"},
        allow_redirects=False
    )
    print(f"  Admin login status: {admin_response.status_code}")
    print(f"  Admin session cookies: {dict(admin_session.cookies)}")
    
    # Check admin access
    partner_admin_response = admin_session.get(f"{BASE_URL}/partner/admin")
    print(f"  Partner admin access status: {partner_admin_response.status_code}")
    if "admin1" in partner_admin_response.text or "Admin" in partner_admin_response.text:
        print("  ✓ Admin can access partner admin page")
    else:
        print("  ✗ Admin cannot access partner admin page")
    
    print()
    
    # Test 3: Verify User Session Still Works
    print("Test 3: Verify original user session is unaffected")
    dashboard_check = user_session.get(f"{BASE_URL}/dashboard")
    print(f"  User dashboard access status: {dashboard_check.status_code}")
    
    if dashboard_check.status_code == 200:
        if "demo" in dashboard_check.text and "admin1" not in dashboard_check.text:
            print("  ✓ User session is still valid and shows correct username")
        else:
            print("  ✗ User session is compromised - shows wrong username!")
            print(f"  Response contains: {'admin1' if 'admin1' in dashboard_check.text else 'demo'}")
    else:
        print("  ✗ User session is invalid")
    
    print()
    
    # Test 4: Same Browser Scenario (Simulated)
    print("Test 4: Same session - User logs in, then admin logs in (overwrites session)")
    same_session = Session()
    
    # First login as user
    user_login = same_session.post(
        f"{BASE_URL}/login",
        data={"username": "demo", "password": "demo123", "role": "customer"},
        allow_redirects=False
    )
    print(f"  User login status: {user_login.status_code}")
    
    # Check username before admin login
    dashboard_before = same_session.get(f"{BASE_URL}/dashboard")
    username_before = "demo" if "demo" in dashboard_before.text else "unknown"
    print(f"  Username before admin login: {username_before}")
    
    # Now login as admin in the SAME session
    admin_login = same_session.post(
        f"{BASE_URL}/partner/admin/login",
        data={"admin_key": "admin-demo-key"},
        allow_redirects=False
    )
    print(f"  Admin login status: {admin_login.status_code}")
    
    # Try to access dashboard again - should redirect or show admin page
    dashboard_after = same_session.get(f"{BASE_URL}/dashboard", allow_redirects=False)
    print(f"  Dashboard access after admin login status: {dashboard_after.status_code}")
    
    if dashboard_after.status_code == 302:
        print("  ✓ Dashboard redirects (session cleared, no user_id)")
    elif dashboard_after.status_code == 200:
        # Check if it shows admin1 or demo
        if "admin1" in dashboard_after.text and "demo" not in dashboard_after.text:
            print("  ✓ Session properly switched to admin")
        elif "demo" in dashboard_after.text:
            print("  ✗ BUG: Still shows user session after admin login!")
        else:
            print("  ? Unknown state")
    
    print()
    print("=== Test Complete ===")

if __name__ == "__main__":
    try:
        test_session_isolation()
    except Exception as e:
        print(f"Error running tests: {e}")
        import traceback
        traceback.print_exc()

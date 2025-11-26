#!/bin/bash
echo "=== Testing Live Session Interference ==="
echo ""

# Simulate two different browsers/sessions
USER_COOKIES=$(mktemp)
ADMIN_COOKIES=$(mktemp)

echo "Step 1: User 'john' logs in (Browser 1)"
curl -s -c $USER_COOKIES -X POST http://localhost:5000/login \
  -d "username=john&password=john123&role=customer" \
  -L -w "\nHTTP: %{http_code}\n" -o /dev/null
echo ""

echo "Step 2: Check user's dashboard (Browser 1)"
USER_DASH=$(curl -s -b $USER_COOKIES http://localhost:5000/dashboard)
if echo "$USER_DASH" | grep -q "john"; then
    echo "  ✓ User dashboard shows 'john'"
elif echo "$USER_DASH" | grep -q "Dashboard"; then
    echo "  ✓ User dashboard accessible (checking username...)"
    # Save to file to inspect
    echo "$USER_DASH" > /tmp/user_before.html
else
    echo "  ✗ User dashboard not accessible"
fi
echo ""

echo "Step 3: Admin logs in (Browser 2 - DIFFERENT SESSION)"
curl -s -c $ADMIN_COOKIES -X POST http://localhost:5000/partner/admin/login \
  -d "admin_key=admin-demo-key" \
  -L -w "\nHTTP: %{http_code}\n" -o /dev/null
echo ""

echo "Step 4: Check admin's page (Browser 2)"
ADMIN_PAGE=$(curl -s -b $ADMIN_COOKIES http://localhost:5000/partner/admin)
if echo "$ADMIN_PAGE" | grep -q "admin1"; then
    echo "  ✓ Admin page shows 'admin1'"
elif echo "$ADMIN_PAGE" | grep -q "Admin"; then
    echo "  ✓ Admin page accessible"
    echo "$ADMIN_PAGE" > /tmp/admin.html
else
    echo "  ✗ Admin page not accessible"
fi
echo ""

echo "Step 5: CRITICAL TEST - Check user's dashboard again (Browser 1)"
echo "  This should STILL show 'john', not 'admin1'"
USER_DASH_AFTER=$(curl -s -b $USER_COOKIES http://localhost:5000/dashboard)

echo "$USER_DASH_AFTER" > /tmp/user_after.html

if echo "$USER_DASH_AFTER" | grep -q "john" && ! echo "$USER_DASH_AFTER" | grep -q "admin1"; then
    echo "  ✓✓✓ PASS: User dashboard still shows 'john'"
elif echo "$USER_DASH_AFTER" | grep -q "admin1"; then
    echo "  ✗✗✗ FAIL: User dashboard now shows 'admin1' - SESSIONS ARE SHARED!"
    echo "  This is the bug - admin login affected user's session"
else
    echo "  ? Unable to determine username in dashboard"
fi
echo ""

echo "Comparing cookies:"
echo "User cookies:"
cat $USER_COOKIES | grep -v "^#"
echo ""
echo "Admin cookies:"
cat $ADMIN_COOKIES | grep -v "^#"
echo ""

# Cleanup
rm -f $USER_COOKIES $ADMIN_COOKIES

echo "=== Test Complete ==="

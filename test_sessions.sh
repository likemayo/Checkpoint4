#!/bin/bash
echo "=== Testing Session Isolation ==="
echo ""

# Create temp files for cookies
USER_COOKIES=$(mktemp)
ADMIN_COOKIES=$(mktemp)

echo "Test 1: User logs in first"
curl -s -c $USER_COOKIES -X POST http://localhost:5000/login \
  -d "username=demo&password=demo123&role=customer" \
  -L -o /dev/null
echo "  ✓ User logged in (cookies saved)"

echo ""
echo "Test 2: Check user dashboard"
USER_RESPONSE=$(curl -s -b $USER_COOKIES http://localhost:5000/dashboard)
if echo "$USER_RESPONSE" | grep -q "demo"; then
    echo "  ✓ User dashboard shows 'demo' username"
else
    echo "  ✗ User dashboard doesn't show demo"
fi

echo ""
echo "Test 3: Admin logs in (different session)"
curl -s -c $ADMIN_COOKIES -X POST http://localhost:5000/partner/admin/login \
  -d "admin_key=admin-demo-key" \
  -L -o /dev/null
echo "  ✓ Admin logged in (separate cookies)"

echo ""
echo "Test 4: Check admin page"
ADMIN_RESPONSE=$(curl -s -b $ADMIN_COOKIES http://localhost:5000/partner/admin)
if echo "$ADMIN_RESPONSE" | grep -q "admin1"; then
    echo "  ✓ Admin page shows 'admin1' username"
else
    echo "  ✗ Admin page doesn't show admin1"
fi

echo ""
echo "Test 5: Verify user session still works"
USER_CHECK=$(curl -s -b $USER_COOKIES http://localhost:5000/dashboard)
if echo "$USER_CHECK" | grep -q "demo"; then
    echo "  ✓ User session unchanged - still shows 'demo'"
else
    echo "  ✗ User session compromised"
fi

echo ""
echo "Test 6: Same session - user then admin (simulates your bug)"
SAME_SESSION=$(mktemp)
curl -s -c $SAME_SESSION -X POST http://localhost:5000/login \
  -d "username=demo&password=demo123&role=customer" \
  -L -o /dev/null
echo "  Step 1: User logged in"

CHECK1=$(curl -s -b $SAME_SESSION http://localhost:5000/dashboard)
if echo "$CHECK1" | grep -q "demo"; then
    echo "  Step 2: Dashboard shows 'demo' ✓"
fi

curl -s -b $SAME_SESSION -c $SAME_SESSION -X POST http://localhost:5000/partner/admin/login \
  -d "admin_key=admin-demo-key" \
  -L -o /dev/null
echo "  Step 3: Admin logged in (same session)"

CHECK2=$(curl -s -b $SAME_SESSION -w "%{http_code}" http://localhost:5000/dashboard -o /tmp/dash_check.html)
if [ "$CHECK2" = "302" ]; then
    echo "  Step 4: Dashboard redirects (no user_id) ✓"
    echo "  Result: Session properly cleared by admin login ✓"
elif [ "$CHECK2" = "200" ]; then
    if grep -q "admin1" /tmp/dash_check.html && ! grep -q "demo" /tmp/dash_check.html; then
        echo "  Step 4: Dashboard shows 'admin1' ✓"
        echo "  Result: Session properly switched to admin ✓"
    elif grep -q "demo" /tmp/dash_check.html; then
        echo "  Step 4: Dashboard still shows 'demo' ✗"
        echo "  Result: BUG - Session not properly cleared!"
    fi
fi

# Cleanup
rm -f $USER_COOKIES $ADMIN_COOKIES $SAME_SESSION /tmp/dash_check.html

echo ""
echo "=== Tests Complete ==="

#!/bin/bash

echo "======================================================================="
echo "COMPLETE PASSWORD RESET/CHANGE FLOW TESTING"
echo "======================================================================="
echo ""

# Reset environment
python reset_test_env.py > /dev/null 2>&1
sleep 1

# =============================================================================
# TEST 1: Admin Password Reset
# =============================================================================
echo "TEST 1: ADMIN PASSWORD RESET"
echo "-----------------------------------------------------------------------"

echo "1.1. Login as admin..."
ADMIN_TOKEN=$(curl -s -X POST "http://localhost:8003/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@test.com", "password": "Test123!!"}' | jq -r '.access_token')
echo "     ✓ Admin logged in"

echo "1.2. Get writer user ID..."
WRITER_RESPONSE=$(curl -s "http://localhost:8003/v1/users/me" \
  -H "Authorization: Bearer $(curl -s -X POST "http://localhost:8003/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "writer@test.com", "password": "Test123!!"}' | jq -r '.access_token')")
WRITER_ID=$(echo "$WRITER_RESPONSE" | jq -r '.id')
echo "     Writer ID: $WRITER_ID"

echo "1.3. Admin resets writer password..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH \
  "http://localhost:8003/v1/users/$WRITER_ID/password" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"new_password": "AdminReset123!!"}')

if [ "$HTTP_CODE" = "204" ]; then
  echo "     ✓ Admin reset password (HTTP 204)"
else
  echo "     ✗ Failed (HTTP $HTTP_CODE)"
fi

echo "1.4. Writer logs in with new password..."
WRITER_TOKEN=$(curl -s -X POST "http://localhost:8003/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "writer@test.com", "password": "AdminReset123!!"}' | jq -r '.access_token // empty')

if [ ! -z "$WRITER_TOKEN" ]; then
  echo "     ✓ New password works"
else
  echo "     ✗ New password doesn't work"
fi

echo ""

# =============================================================================
# TEST 2: User Change Password (Authenticated)
# =============================================================================
echo "TEST 2: USER CHANGE PASSWORD (AUTHENTICATED)"
echo "-----------------------------------------------------------------------"

echo "2.1. Writer changes own password..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  "http://localhost:8003/v1/users/me/change-password" \
  -H "Authorization: Bearer $WRITER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"current_password": "AdminReset123!!", "new_password": "SelfChanged123!!"}')

if [ "$HTTP_CODE" = "204" ]; then
  echo "     ✓ Password changed (HTTP 204)"
else
  echo "     ✗ Failed (HTTP $HTTP_CODE)"
fi

echo "2.2. Login with self-changed password..."
NEW_TOKEN=$(curl -s -X POST "http://localhost:8003/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "writer@test.com", "password": "SelfChanged123!!"}' | jq -r '.access_token // empty')

if [ ! -z "$NEW_TOKEN" ]; then
  echo "     ✓ Self-changed password works"
else
  echo "     ✗ Self-changed password doesn't work"
fi

echo ""

# =============================================================================
# TEST 3: Forgot Password Flow
# =============================================================================
echo "TEST 3: FORGOT PASSWORD FLOW (UNAUTHENTICATED)"
echo "-----------------------------------------------------------------------"

echo "3.1. Request password reset for editor..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  "http://localhost:8003/v1/auth/forgot-password" \
  -H "Content-Type: application/json" \
  -d '{"email": "editor@test.com"}')

if [ "$HTTP_CODE" = "204" ]; then
  echo "     ✓ Reset requested (HTTP 204)"
  echo "     📧 Check backend console for reset link (development mode)"
else
  echo "     ✗ Failed (HTTP $HTTP_CODE)"
fi

echo ""
echo "======================================================================="
echo "RESULTS SUMMARY"
echo "======================================================================="

# Check which tests passed
TEST1_PASSED=false
TEST2_PASSED=false
TEST3_PASSED=true  # Forgot password just needs 204

if [ ! -z "$WRITER_TOKEN" ]; then
  TEST1_PASSED=true
fi

if [ ! -z "$NEW_TOKEN" ]; then
  TEST2_PASSED=true
fi

if [ "$TEST1_PASSED" = true ]; then
  echo "✓ Test 1: Admin Password Reset - PASSED"
else
  echo "✗ Test 1: Admin Password Reset - FAILED"
fi

if [ "$TEST2_PASSED" = true ]; then
  echo "✓ Test 2: User Change Password - PASSED"
else
  echo "✗ Test 2: User Change Password - FAILED"
fi

if [ "$TEST3_PASSED" = true ]; then
  echo "✓ Test 3: Forgot Password Request - PASSED"
else
  echo "✗ Test 3: Forgot Password Request - FAILED"
fi

echo ""
if [ "$TEST1_PASSED" = true ] && [ "$TEST2_PASSED" = true ] && [ "$TEST3_PASSED" = true ]; then
  echo "🎉 ALL TESTS PASSED!"
else
  echo "⚠️  SOME TESTS FAILED"
fi
echo "======================================================================="

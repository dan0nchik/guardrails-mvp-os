#!/bin/bash
# Quick API test script

set -e

API_URL="${API_URL:-http://localhost:8000}"

echo "Testing Guardrails MVP API at $API_URL"
echo ""

# Health check
echo "1. Health check..."
curl -s "$API_URL/health" | jq .
echo ""

# Test chat request
echo "2. Test chat request (weather)..."
curl -s -X POST "$API_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session-001",
    "user_message": "What is the weather in San Francisco?",
    "agent_profile": "default"
  }' | jq .
echo ""

# Test chat request (search)
echo "3. Test chat request (search)..."
curl -s -X POST "$API_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session-002",
    "user_message": "Search for information about AI safety",
    "agent_profile": "default"
  }' | jq .
echo ""

echo "Tests completed!"

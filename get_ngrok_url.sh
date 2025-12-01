#!/bin/bash
# Get the current ngrok public URL

echo "🌐 Fetching ngrok public URL..."
echo ""

URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys, json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null)

if [ -z "$URL" ]; then
    echo "❌ Error: Could not retrieve ngrok URL"
    echo "   Make sure the services are running: docker compose up -d"
    exit 1
fi

echo "✅ GrokProxy is accessible at:"
echo ""
echo "   $URL"
echo ""
echo "📊 Ngrok Dashboard: http://localhost:4040"
echo "🔧 Local Access: http://localhost:8080"
echo ""
echo "Example API call:"
echo "curl -H 'Authorization: Bearer YOUR_API_KEY' \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"model\":\"grok-latest\",\"messages\":[{\"role\":\"user\",\"content\":\"Hello!\"}]}' \\"
echo "     $URL/v1/chat/completions"
echo ""

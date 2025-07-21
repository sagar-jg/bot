#!/bin/bash

echo "🔄 Restarting WhatsApp Bot API..."

# Stop the application
bash scripts/stop.sh

# Wait a moment
sleep 3

# Start the application
bash scripts/deploy.sh

echo "✅ WhatsApp Bot API restarted successfully"

#!/bin/bash

echo "================================================="
echo "   🤖 RAG Project Environment Setup Script"
echo "================================================="
echo ""

# 1. Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "❌ ERROR: Docker is not running."
  echo "Please start Docker Desktop and try again."
  exit 1
fi

echo "✅ Docker is running."
echo "🔄 Starting PostgreSQL Vector Database..."
docker compose up -d

echo ""
echo "🔄 Setting up Python Virtual Environment..."

# 2. Setup VENV
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtual environment created."
else
    echo "✅ Virtual environment already exists."
fi

# 3. Install Requirements
echo "🔄 Installing Python dependencies..."
source venv/bin/activate
pip install -r requirements.txt
echo "✅ Dependencies installed."

echo ""
echo "================================================="
echo "🎉 SETUP COMPLETE!"
echo "================================================="
echo "Your environment is fully prepared."
echo ""
echo "NEXT STEPS:"
echo "1. Create your .env file with your FIREWORKS_API_KEY."
echo "2. Open pgAdmin4 and run the code from init.sql in the Query Tool to build the tables."
echo "3. Run 'source venv/bin/activate' to start working."
echo "================================================="

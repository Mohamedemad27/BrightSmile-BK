#!/bin/bash

# Start script for local development without Docker

echo "🚀 Starting Bright Smile Backend (Local Development)"
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Please create one first:"
    echo "   python3 -m venv .venv"
    echo "   source .venv/bin/activate"
    echo "   pip install -r requirements.txt"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Please create one:"
    echo "   cp .env.template .env"
    echo "   # Then edit .env with your settings"
    exit 1
fi

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠️  Redis is not running. Starting Redis..."
    if command -v brew > /dev/null 2>&1; then
        brew services start redis
    else
        echo "❌ Please start Redis manually"
        exit 1
    fi
fi

# Check if PostgreSQL is running
if ! pg_isready > /dev/null 2>&1; then
    echo "⚠️  PostgreSQL is not running. Please start it:"
    if command -v brew > /dev/null 2>&1; then
        echo "   brew services start postgresql@17"
    else
        echo "   sudo systemctl start postgresql"
    fi
    exit 1
fi

echo "✅ All services are ready"
echo ""
echo "Starting components in separate terminals..."
echo ""
echo "1. Open a new terminal and run: celery -A project worker --loglevel=info"
echo "2. Open another terminal and run: celery -A project beat --loglevel=info"
echo "3. This terminal will run the Django development server"
echo ""
read -p "Press Enter when Celery worker and beat are running..."

# Activate virtual environment
source .venv/bin/activate

# Run migrations
echo "Running migrations..."
python manage.py migrate

# Start Django development server
echo ""
echo "🌟 Starting Django development server..."
python manage.py runserver

#!/bin/bash
# Start backend, frontend and Mailpit (local dev)

cd "$(dirname "$0")"

# Mailpit
docker run -d --rm --name opr-mailpit -p 1025:1025 -p 8025:8025 axllent/mailpit 2>/dev/null \
  || docker start opr-mailpit 2>/dev/null \
  || true

# Backend
cd backend
MAILPIT_HOST=localhost ../venv/bin/uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Frontend
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo "Backend  : http://localhost:8000"
echo "Frontend : http://localhost:4321"
echo "Mailpit  : http://localhost:8025"
echo "Press Ctrl+C to stop."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; docker stop opr-mailpit 2>/dev/null; exit" INT TERM
wait

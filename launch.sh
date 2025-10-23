#!/bin/bash

CURRENT_DIR="$(cd "$(dirname "$0")" && pwd)"

cleanup() {
  trap - INT TERM
  # Send signals to entire process groups so child processes (e.g., Flask reloader) also exit
  if [ -n "${BACKEND_PID:-}" ]; then
    local target="${BACKEND_PGID:-$BACKEND_PID}"
    kill -TERM -"$target" 2>/dev/null || true
  fi
  if [ -n "${FRONTEND_PID:-}" ]; then
    local target="${FRONTEND_PGID:-$FRONTEND_PID}"
    kill -TERM -"$target" 2>/dev/null || true
  fi
  sleep 1
  if [ -n "${BACKEND_PID:-}" ]; then
    local target="${BACKEND_PGID:-$BACKEND_PID}"
    kill -KILL -"$target" 2>/dev/null || true
  fi
  if [ -n "${FRONTEND_PID:-}" ]; then
    local target="${FRONTEND_PGID:-$FRONTEND_PID}"
    kill -KILL -"$target" 2>/dev/null || true
  fi
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}

trap 'echo; echo "Shutting down..."; cleanup' INT TERM

( cd "$CURRENT_DIR/backend" && uv sync && exec uv run python app.py ) &
BACKEND_PID=$!
BACKEND_PGID=$(ps -o pgid= -p "$BACKEND_PID" | tr -d ' ')

sleep 3
( cd "$CURRENT_DIR/frontend" && exec npm start ) &
FRONTEND_PID=$!
FRONTEND_PGID=$(ps -o pgid= -p "$FRONTEND_PID" | tr -d ' ')

sleep 10

echo "Backend PID: $BACKEND_PID  Frontend PID: $FRONTEND_PID"
echo "Press Ctrl-C to stop both."

wait "$BACKEND_PID" "$FRONTEND_PID"

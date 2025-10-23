#!/bin/bash

# Run the backend
cd $(dirname $0)/backend
uv sync
uv run python app.py &

# Run the frontend
cd $(dirname $0)/frontend
npm start
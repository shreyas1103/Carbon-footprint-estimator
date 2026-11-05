#!/bin/bash

python -m streamlit run dashboard/app.py \
    --server.address=0.0.0.0 \
    --server.port=8000 \
    --server.headless=true
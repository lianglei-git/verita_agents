#!/bin/bash
# Run golden case tests with LLM configuration

export OPENAI_API_KEY="aaa"
export OPENAI_BASE_URL="http://10.2.112.180:9998/v1/"
export LLM_MODEL="qwen2.5-3b"

cd "$(dirname "$0")"

echo "Running agent on golden cases with LLM..."
python run_golden_tests.py

if [ -f "test_outputs.json" ]; then
    echo ""
    echo "Running acceptance scoring..."
    python ega_score.py test_outputs.json
fi

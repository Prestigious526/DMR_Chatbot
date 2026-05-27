#!/bin/bash
# setup_llm.sh
# One-shot script to install Ollama and pull the recommended model.
# Run: bash scripts/setup_llm.sh

set -e

echo ""
echo "=== DMR HHPC Chatbot — LLM Setup ==="
echo ""

# Detect OS
OS="$(uname -s)"

# ── Install Ollama ─────────────────────────────────────────────
if command -v ollama &>/dev/null; then
  echo "[✓] Ollama already installed: $(ollama --version)"
else
  echo "[→] Installing Ollama..."
  if [ "$OS" = "Linux" ]; then
    curl -fsSL https://ollama.com/install.sh | sh
  elif [ "$OS" = "Darwin" ]; then
    echo "    On macOS, download from https://ollama.com/download"
    echo "    or run: brew install ollama"
    exit 1
  else
    echo "    On Windows, download from https://ollama.com/download"
    exit 1
  fi
fi

# ── Start Ollama server ────────────────────────────────────────
echo ""
echo "[→] Starting Ollama server in background..."
ollama serve &>/dev/null &
sleep 3

# ── Pull model ────────────────────────────────────────────────
MODEL="${1:-phi3:mini}"
echo "[→] Pulling model: $MODEL"
echo "    (This downloads ~2.2 GB for phi3:mini — one time only)"
echo ""
ollama pull "$MODEL"

echo ""
echo "[✓] LLM setup complete!"
echo ""
echo "    Model  : $MODEL"
echo "    Backend: ollama"
echo ""
echo "    Create a .env file in the project root:"
echo "    ----------------------------------------"
echo "    LLM_BACKEND=ollama"
echo "    LLM_MODEL=$MODEL"
echo "    ----------------------------------------"
echo ""
echo "    Then start the chatbot:"
echo "    cd backend && python server.py"
echo ""

# ── Alternative: llama.cpp GGUF models ────────────────────────
echo "--- Alternative: llama-cpp-python (no separate process) ---"
echo ""
echo "  1. Download a GGUF model:"
echo "     Phi-3 Mini Q4:   https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf"
echo "     TinyLlama Q4:    https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF"
echo "     Gemma 2B Q4:     https://huggingface.co/google/gemma-2b-it-gguf"
echo ""
echo "  2. Place the .gguf file in models/"
echo ""
echo "  3. Set .env:"
echo "     LLM_BACKEND=llamacpp"
echo "     LLM_MODEL_PATH=models/phi-3-mini-q4.gguf"
echo ""
echo "  4. Install: pip install llama-cpp-python"
echo ""

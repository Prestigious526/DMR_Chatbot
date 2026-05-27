# DMR HHPC Fault Diagnosis Chatbot

## Architecture Overview

```
User Query
    │
    ▼
┌─────────────────────────────────┐
│   TIER 1: Rule Engine + Classifier  │  ← Fast, offline, zero RAM
│   (classifier.py + rule_engine.py)  │
│   Source: Fault_Diagnosis_RAG.md    │
└───────────────┬─────────────────┘
                │ Unresolved / "I need more info"
                ▼
┌─────────────────────────────────┐
│   TIER 2: RAG + Tiny LLM        │  ← Offline, ~2-4 GB RAM
│   (rag_engine.py + llm.py)      │
│   Source: Both documents        │
└─────────────────────────────────┘
```

## Tier 1 — Rule Engine + Keyword Classifier
- **Speed**: Instant (microseconds)
- **RAM**: < 50 MB
- **Source doc**: `Fault_Diagnosis_RAG.md`
- **How it works**: TF-IDF keyword scoring routes the query to one of 5 structured
  procedures. The rule engine walks the user through yes/no decision trees.
- **Escalation trigger**: User clicks "Can't resolve — ask AI" or query scores < 0.3

## Tier 2 — RAG + Tiny Quantized LLM
- **Speed**: 5–30s per response (hardware dependent)
- **RAM**: 2–4 GB (Q4 quantized model)
- **Source docs**: `Fault_Diagnosis_RAG.md` + `Secure_Part1.md`
- **How it works**:
  1. Query is embedded using a tiny sentence encoder
  2. Top-K relevant chunks are retrieved from both documents
  3. Chunks + query are passed to a local LLM (llama.cpp / Ollama)
  4. LLM generates a contextual answer grounded in the documents

## Recommended LLM Options (offline, low memory)

| Model | RAM Required | Speed | Notes |
|-------|-------------|-------|-------|
| Phi-3 Mini 4K Q4 | ~2.2 GB | Fast | Best for this use case |
| TinyLlama 1.1B Q4 | ~0.7 GB | Very fast | Less accurate |
| Gemma 2B Q4 | ~1.5 GB | Fast | Good balance |
| Mistral 7B Q4 | ~4.5 GB | Moderate | Most accurate |

## Project Structure

```
dmr_chatbot/
├── backend/
│   ├── classifier.py        ← Keyword-based fault classifier (Tier 1)
│   ├── rule_engine.py       ← State-machine decision tree (Tier 1)
│   ├── rag_engine.py        ← Document chunking + retrieval (Tier 2)
│   ├── llm.py               ← LLM interface (Ollama / llama.cpp) (Tier 2)
│   ├── session_manager.py   ← Orchestrates Tier 1 → Tier 2 escalation
│   └── server.py            ← Flask REST API
├── frontend/
│   ├── index.html           ← Main chat UI
│   └── static/
│       ├── js/
│       │   ├── api.js       ← Backend API client
│       │   ├── ui.js        ← DOM rendering
│       │   └── chat.js      ← App controller
│       └── css/
│           └── style.css    ← Styles
├── data/
│   ├── procedures.json          ← Encoded decision trees (Tier 1)
│   ├── Fault_Diagnosis_RAG.md   ← Source doc 1
│   └── Secure_Part1.md          ← Source doc 2
├── models/                      ← Place downloaded GGUF models here
├── scripts/
│   └── setup_llm.sh             ← One-shot LLM setup script
└── requirements.txt
```

## Quick Start

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 2. Place your documents
```bash
cp Fault_Diagnosis_RAG.md data/
cp Secure_Part1.md data/
```

### 3. Build the RAG index (one-time)
```bash
cd backend
python rag_engine.py --build
```

### 4. Set up LLM (optional — for Tier 2)
```bash
# Install Ollama (recommended)
bash scripts/setup_llm.sh

# OR manually place a GGUF model in models/ and set in .env:
# LLM_BACKEND=llamacpp
# LLM_MODEL_PATH=models/phi-3-mini-q4.gguf
```

### 5. Run the server
```bash
cd backend
python server.py
# Open http://localhost:5000
```

## Environment Variables (.env)

```
LLM_BACKEND=ollama          # "ollama" | "llamacpp" | "none"
LLM_MODEL=phi3:mini         # Ollama model name
LLM_MODEL_PATH=models/phi-3-mini-q4.gguf  # For llamacpp
LLM_TIMEOUT=60              # Max seconds to wait for LLM response
RAG_TOP_K=4                 # Number of chunks to retrieve
RAG_CHUNK_SIZE=400          # Characters per chunk
TIER1_CONFIDENCE_THRESHOLD=0.3  # Below this → escalate to Tier 2
```

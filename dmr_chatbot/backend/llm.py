"""
llm.py  —  Tier 2
------------------
LLM interface for the DMR HHPC chatbot, built with LangChain.

Supports two offline backends:
  A) Ollama    — recommended, easiest setup (ollama serve + ollama pull phi3:mini)
  B) llama-cpp-python — direct GGUF file loading, no separate process needed

Uses LangChain for:
  - Structured prompt templates (ChatPromptTemplate)
  - LLM wrappers (ChatOllama / LlamaCpp)
  - RetrievalQA chain for end-to-end RAG queries

Falls back gracefully if LLM is unavailable (returns None -> UI shows fallback msg).
"""

from __future__ import annotations
import os, time, textwrap
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config  (set via .env or environment variables)
# ---------------------------------------------------------------------------
LLM_BACKEND    = os.getenv("LLM_BACKEND", "ollama")        # "ollama" | "llamacpp" | "none"
LLM_MODEL      = os.getenv("LLM_MODEL", "phi3:mini")       # Ollama model name
LLM_MODEL_PATH = os.getenv("LLM_MODEL_PATH", "")           # Path to .gguf for llamacpp
LLM_TIMEOUT    = int(os.getenv("LLM_TIMEOUT", "60"))       # Seconds
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "512"))
LLM_TEMPERATURE= float(os.getenv("LLM_TEMPERATURE", "0.1"))  # Low = more factual
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = textwrap.dedent("""\
You are an expert fault diagnosis assistant for the Secure HHPC — a DMR VHF handheld radio.
Your job is to help field technicians diagnose and fix faults by answering questions
about the radio's operation, specifications, and troubleshooting procedures.

RULES:
1. Answer ONLY based on the provided context documents.
2. If the answer is not in the context, say: "I don't have enough information in my documents to answer this. Please consult the full technical manual."
3. Be concise and practical. Technicians need clear, actionable answers.
4. When referring to test points, components, or measurements, be precise.
5. If a fault troubleshooting procedure applies, refer the user to run the structured diagnostic.
6. Do NOT make up component names, voltages, or procedures.
""")


# ---------------------------------------------------------------------------
# LangChain Prompt Template
# ---------------------------------------------------------------------------
def _build_prompt_template():
    """Build a ChatPromptTemplate for the RAG chain."""
    from langchain_core.prompts import ChatPromptTemplate

    return ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", (
            "Use the following context documents to answer the question.\n\n"
            "CONTEXT:\n{context}\n\n"
            "QUESTION: {input}\n\n"
            "Provide a clear, concise answer based only on the context above."
        )),
    ])


# ---------------------------------------------------------------------------
# LLM Backend Factory
# ---------------------------------------------------------------------------
def _create_llm(backend: str):
    """
    Create a LangChain LLM instance based on the configured backend.
    Returns (llm_instance, is_available: bool).
    """
    if backend == "ollama":
        return _create_ollama_llm()
    elif backend == "llamacpp":
        return _create_llamacpp_llm()
    else:
        return None, False


def _create_ollama_llm():
    """Create a LangChain ChatOllama instance."""
    try:
        from langchain_ollama import ChatOllama

        llm = ChatOllama(
            model=LLM_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=LLM_TEMPERATURE,
            num_predict=LLM_MAX_TOKENS,
            timeout=LLM_TIMEOUT,
        )

        # Test connectivity
        try:
            import ollama as ollama_client
            ollama_client.list()
            print(f"[LLM] Ollama backend ready (model: {LLM_MODEL})")
            return llm, True
        except Exception:
            # Try a lightweight invocation to check
            try:
                llm.invoke("test")
                print(f"[LLM] Ollama backend ready (model: {LLM_MODEL})")
                return llm, True
            except Exception as e:
                print(f"[LLM] Ollama not available: {e}")
                return llm, False

    except ImportError:
        print("[LLM] langchain-ollama not installed.")
        return None, False


def _create_llamacpp_llm():
    """Create a LangChain LlamaCpp instance."""
    try:
        from langchain_community.llms import LlamaCpp

        if not LLM_MODEL_PATH or not os.path.exists(LLM_MODEL_PATH):
            print(f"[LLM] GGUF model not found at: {LLM_MODEL_PATH}")
            return None, False

        llm = LlamaCpp(
            model_path=LLM_MODEL_PATH,
            n_ctx=2048,
            n_threads=os.cpu_count() or 4,
            max_tokens=LLM_MAX_TOKENS,
            temperature=LLM_TEMPERATURE,
            verbose=False,
        )
        print(f"[LLM] LlamaCpp backend ready (model: {LLM_MODEL_PATH})")
        return llm, True

    except ImportError:
        print("[LLM] llama-cpp-python not installed.")
        return None, False


# ---------------------------------------------------------------------------
# LLM Manager — public interface
# ---------------------------------------------------------------------------
class LLMManager:
    """
    Auto-selects the correct LangChain LLM backend and provides both:
      - query()            : manual context injection (backward compat)
      - query_with_chain() : full LangChain RetrievalQA chain
    """

    def __init__(self):
        self._llm = None
        self._available: Optional[bool] = None
        self._chain = None

    def _init_llm(self):
        """Lazy-initialize the LLM backend."""
        if self._llm is None and self._available is None:
            self._llm, self._available = _create_llm(LLM_BACKEND.lower())
            if not self._available:
                print(f"[LLM] Backend '{LLM_BACKEND}' is NOT available. Tier 2 disabled.")

    def is_available(self) -> bool:
        self._init_llm()
        return bool(self._available)

    def query(self, user_question: str, context: str) -> dict:
        """
        Run a RAG-grounded LLM query with manually provided context.
        Backward-compatible interface used by session_manager.py.

        Args:
            user_question: The user's free-text question
            context:       Pre-formatted context string from RAGEngine.format_context()

        Returns:
            {
                "answer": str,
                "success": bool,
                "latency_ms": int,
                "error": str | None
            }
        """
        if not self.is_available():
            return {
                "answer": None,
                "success": False,
                "latency_ms": 0,
                "error": f"LLM backend '{LLM_BACKEND}' is not available. "
                         f"Please install and start Ollama, or set LLM_BACKEND=none in .env.",
            }

        prompt = _build_prompt_template()
        chain = prompt | self._llm

        t0 = time.time()
        try:
            response = chain.invoke({
                "context": context,
                "input": user_question,
            })

            # Extract text from response (handles both ChatModel and LLM responses)
            if hasattr(response, "content"):
                answer = response.content.strip()
            else:
                answer = str(response).strip()

            return {
                "answer": answer,
                "success": True,
                "latency_ms": int((time.time() - t0) * 1000),
                "error": None,
            }
        except Exception as e:
            return {
                "answer": None,
                "success": False,
                "latency_ms": int((time.time() - t0) * 1000),
                "error": str(e),
            }

    def query_with_chain(self, question: str, retriever) -> dict:
        """
        Run a full LangChain RetrievalQA chain.

        This is the proper LangChain RAG flow:
          retriever fetches docs → prompt template injects context → LLM generates

        Args:
            question:  The user's question
            retriever: A LangChain retriever (from RAGEngine.get_retriever())

        Returns:
            Same dict format as query()
        """
        if not self.is_available():
            return {
                "answer": None,
                "success": False,
                "latency_ms": 0,
                "error": f"LLM backend '{LLM_BACKEND}' is not available.",
            }

        t0 = time.time()
        try:
            from langchain.chains import create_retrieval_chain
            from langchain.chains.combine_documents import create_stuff_documents_chain

            prompt = _build_prompt_template()

            # Build the chain: retriever → stuff docs into prompt → LLM
            combine_docs_chain = create_stuff_documents_chain(self._llm, prompt)
            rag_chain = create_retrieval_chain(retriever, combine_docs_chain)

            result = rag_chain.invoke({"input": question})

            answer = result.get("answer", "")
            if not answer and "result" in result:
                answer = result["result"]

            return {
                "answer": answer.strip() if answer else "",
                "success": True,
                "latency_ms": int((time.time() - t0) * 1000),
                "error": None,
            }
        except Exception as e:
            return {
                "answer": None,
                "success": False,
                "latency_ms": int((time.time() - t0) * 1000),
                "error": str(e),
            }

    def get_backend_info(self) -> dict:
        return {
            "backend": LLM_BACKEND,
            "model": LLM_MODEL if LLM_BACKEND == "ollama" else LLM_MODEL_PATH,
            "available": self.is_available(),
            "framework": "langchain",
        }


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    manager = LLMManager()
    print(f"Backend info: {manager.get_backend_info()}")

    if manager.is_available():
        test_context = """
[Source 1: Fault_Diagnosis_RAG.md]
The Radio set features a modular physical design. When the Receiver Transmitter
develops a fault, follow the troubleshooting procedures outlined below.
Procedure 4: Receiver Path Troubleshooting. Check RSSI display when RF is turned on.

[Source 2: Secure_Part1.md]
Frequency range: 136-174 MHz. Channel spacing: 12.5 kHz in DMR mode / 25 kHz in analog.
Digital Sensitivity: minimum -117dBm for 5% BER.
"""
        result = manager.query(
            user_question="What is the frequency range of the Secure HHPC?",
            context=test_context,
        )
        print(f"\nAnswer: {result['answer']}")
        print(f"Latency: {result['latency_ms']} ms")
    else:
        print("LLM not available — check your backend setup.")

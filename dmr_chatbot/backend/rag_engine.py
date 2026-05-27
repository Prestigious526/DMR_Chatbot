"""
rag_engine.py  —  Tier 2
------------------------
Retrieval-Augmented Generation engine for the DMR HHPC chatbot.
Built with LangChain for proper document loading, chunking, embedding,
and vector-store-backed retrieval.

Pipeline:
  1. Load markdown source documents
  2. Split using RecursiveCharacterTextSplitter (markdown-aware separators)
  3. Embed using HuggingFace all-MiniLM-L6-v2
  4. Store in FAISS vector store (persisted to disk)
  5. Expose retriever for RetrievalQA chain integration
"""

from __future__ import annotations
import os, argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Paths & Config
# ---------------------------------------------------------------------------
_HERE  = Path(__file__).parent
_DATA  = (_HERE / ".." / "data").resolve()
_FAISS_DIR = _DATA / "faiss_index"

RAG_CHUNK_SIZE    = int(os.getenv("RAG_CHUNK_SIZE", "600"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "100"))
RAG_TOP_K         = int(os.getenv("RAG_TOP_K", "4"))
EMBEDDING_MODEL   = os.getenv("RAG_EMBEDDING_MODEL", "all-MiniLM-L6-v2")

SOURCE_DOCS = [
    _DATA / "Fault_Diagnosis_RAG.md",
    _DATA / "Secure_Part1.md",
]


# ---------------------------------------------------------------------------
# Data model  (kept for backward-compat with session_manager.py)
# ---------------------------------------------------------------------------
@dataclass
class RetrievedChunk:
    doc_name: str
    chunk_id: int
    text: str
    score: float


# ---------------------------------------------------------------------------
# RAGEngine — LangChain-based
# ---------------------------------------------------------------------------
class RAGEngine:
    """
    LangChain-powered retrieval engine.

    Uses:
      - RecursiveCharacterTextSplitter with markdown separators
      - HuggingFaceEmbeddings (all-MiniLM-L6-v2)
      - FAISS vector store with local persistence

    Call build_index() once, then retrieve() or get_retriever() at runtime.
    """

    def __init__(self):
        self._vectorstore = None
        self._embeddings  = None

    # ------------------------------------------------------------------
    # Embeddings (lazy-loaded, reused)
    # ------------------------------------------------------------------
    def _get_embeddings(self):
        if self._embeddings is None:
            from langchain_huggingface import HuggingFaceEmbeddings
            print(f"[RAG] Loading embedding model: {EMBEDDING_MODEL}...")
            self._embeddings = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
            print("[RAG] Embedding model ready.")
        return self._embeddings

    # ------------------------------------------------------------------
    # Index building
    # ------------------------------------------------------------------
    def build_index(self, force: bool = False) -> None:
        """
        Load documents, chunk, embed, and persist FAISS index to disk.
        Skips rebuild if index already exists on disk (unless force=True).
        """
        if not force and _FAISS_DIR.exists() and (_FAISS_DIR / "index.faiss").exists():
            print("[RAG] Loading existing FAISS index from disk...")
            self._load_index()
            return

        print("[RAG] Building new FAISS index...")
        documents = self._load_documents()
        if not documents:
            raise RuntimeError(
                "No documents found in data/. "
                "Ensure Fault_Diagnosis_RAG.md and Secure_Part1.md exist."
            )

        chunks = self._split_documents(documents)
        print(f"[RAG] Total chunks after splitting: {len(chunks)}")

        self._build_vectorstore(chunks)
        self._save_index()
        print(f"[RAG] FAISS index built and saved to {_FAISS_DIR}")

    def _load_documents(self):
        """Load markdown documents using LangChain TextLoader."""
        from langchain_community.document_loaders import TextLoader

        all_docs = []
        for doc_path in SOURCE_DOCS:
            if not doc_path.exists():
                print(f"[RAG] WARNING: {doc_path} not found — skipping.")
                continue
            loader = TextLoader(str(doc_path), encoding="utf-8")
            docs = loader.load()
            # Tag each document with its source filename
            for doc in docs:
                doc.metadata["source"] = doc_path.name
            all_docs.extend(docs)
            print(f"[RAG] Loaded: {doc_path.name} ({len(docs)} document(s))")
        return all_docs

    def _split_documents(self, documents):
        """
        Split documents using RecursiveCharacterTextSplitter with
        markdown-aware separators so section boundaries are respected.
        """
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=RAG_CHUNK_SIZE,
            chunk_overlap=RAG_CHUNK_OVERLAP,
            separators=[
                "\n## ",      # H2 headers (procedure boundaries)
                "\n### ",     # H3 headers (sub-sections)
                "\n#### ",    # H4 headers (branches)
                "\n---",      # Horizontal rules
                "\n\n",       # Paragraph breaks
                "\n",         # Line breaks
                ". ",         # Sentence boundaries
                " ",          # Word boundaries (last resort)
            ],
            keep_separator=True,
            strip_whitespace=True,
        )

        chunks = splitter.split_documents(documents)

        # Add chunk_id metadata for backward compat
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_id"] = i

        print(f"[RAG] Split into {len(chunks)} chunks "
              f"(size={RAG_CHUNK_SIZE}, overlap={RAG_CHUNK_OVERLAP})")
        return chunks

    def _build_vectorstore(self, chunks):
        """Create FAISS vector store from document chunks."""
        from langchain_community.vectorstores import FAISS

        embeddings = self._get_embeddings()
        self._vectorstore = FAISS.from_documents(
            documents=chunks,
            embedding=embeddings,
        )

    def _save_index(self):
        """Persist FAISS index to disk."""
        if self._vectorstore is not None:
            _FAISS_DIR.mkdir(parents=True, exist_ok=True)
            self._vectorstore.save_local(str(_FAISS_DIR))

    def _load_index(self):
        """Load FAISS index from disk."""
        from langchain_community.vectorstores import FAISS

        embeddings = self._get_embeddings()
        self._vectorstore = FAISS.load_local(
            str(_FAISS_DIR),
            embeddings,
            allow_dangerous_deserialization=True,
        )
        print(f"[RAG] FAISS index loaded ({self._vectorstore.index.ntotal} vectors)")

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    def retrieve(self, query: str, top_k: int = RAG_TOP_K) -> list[RetrievedChunk]:
        """
        Retrieve the top-k most relevant chunks for a query.
        Returns RetrievedChunk objects for backward compatibility.
        """
        if self._vectorstore is None:
            self.build_index()

        results = self._vectorstore.similarity_search_with_score(query, k=top_k)

        retrieved = []
        for doc, score in results:
            # FAISS returns L2 distance; convert to a 0-1 similarity score
            # Lower distance = more similar. Use 1/(1+d) for normalization.
            similarity = round(1.0 / (1.0 + float(score)), 4)
            retrieved.append(RetrievedChunk(
                doc_name=doc.metadata.get("source", "unknown"),
                chunk_id=doc.metadata.get("chunk_id", 0),
                text=doc.page_content,
                score=similarity,
            ))
        return retrieved

    def get_retriever(self, top_k: int = RAG_TOP_K):
        """
        Return a LangChain retriever for use in RetrievalQA chains.
        Uses MMR (Maximal Marginal Relevance) for diverse results.
        """
        if self._vectorstore is None:
            self.build_index()

        return self._vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": top_k,
                "fetch_k": top_k * 3,  # fetch more candidates for MMR
            },
        )

    def format_context(self, chunks: list[RetrievedChunk]) -> str:
        """Format retrieved chunks into a prompt-ready context string."""
        parts = []
        for i, c in enumerate(chunks, 1):
            parts.append(f"[Source {i}: {c.doc_name} | Relevance: {c.score}]\n{c.text}")
        return "\n\n---\n\n".join(parts)

    def is_ready(self) -> bool:
        return self._vectorstore is not None


# ---------------------------------------------------------------------------
# CLI — build / query index
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DMR RAG Index Builder (LangChain + FAISS)")
    parser.add_argument("--build", action="store_true", help="Build/rebuild the FAISS index")
    parser.add_argument("--query", type=str, help="Test a query against the index")
    parser.add_argument("--top-k", type=int, default=RAG_TOP_K, help="Number of results")
    args = parser.parse_args()

    engine = RAGEngine()

    if args.build:
        engine.build_index(force=True)
    else:
        engine.build_index()

    if args.query:
        results = engine.retrieve(args.query, top_k=args.top_k)
        print(f"\nQuery: {args.query!r}")
        print(f"Top {len(results)} chunks:\n")
        for r in results:
            print(f"  [{r.doc_name}  score={r.score}]")
            print(f"  {r.text[:200]}...")
            print()

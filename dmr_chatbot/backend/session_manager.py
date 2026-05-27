"""
session_manager.py  —  Orchestration Layer
-------------------------------------------
Ties Tier 1 (classifier + rule engine) and Tier 2 (RAG + LLM) together.

Flow:
  User input
      |
      v
  [Tier 1] Classifier -> high confidence? -> Rule Engine (step-by-step)
      |
      | low confidence OR user clicks "Ask AI"
      v
  [Tier 2] RAG retrieve chunks -> LLM generates answer

Escalation triggers:
  1. Classifier confidence < ESCALATION_THRESHOLD
  2. User explicitly clicks "This didn't help — ask AI"
  3. User is in a procedure and types a general question (not yes/no)
"""

from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from typing import Optional

from classifier import classify, parse_yes_no, ClassifierOutput
from rule_engine import RuleEngine, Session as EngineSession, Step, DiagnosisResult


@dataclass
class ChatResponse:
    message_type: str
    # message_type values:
    #   greeting, classify_ask, question, result, rag_answer,
    #   rag_unavailable, info, error

    text: str
    session_id: Optional[str] = None

    # Tier 1 fields
    procedure_id: Optional[str] = None
    procedure_name: Optional[str] = None
    step_number: Optional[int] = None
    test_point: Optional[str] = None
    target_value: Optional[str] = None
    component: Optional[str] = None
    action: Optional[str] = None
    is_ok: Optional[bool] = None
    show_yes_no: bool = False
    candidates: Optional[list[dict]] = None
    all_procedures: Optional[list[dict]] = None

    # Tier 2 fields
    rag_chunks: Optional[list[dict]] = None     # sources shown to user
    llm_latency_ms: Optional[int] = None
    tier: int = 1                               # 1 or 2 — shown in UI badge

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class ChatbotSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    phase: str = "GREET"
    # phases: GREET | CLASSIFY | PROCEDURE | DONE | RAG
    engine_session: Optional[EngineSession] = None


class SessionManager:
    """
    One instance lives for the server's lifetime.
    Manages all concurrent user sessions.
    """

    def __init__(self):
        self._engine = RuleEngine()
        self._sessions: dict[str, ChatbotSession] = {}
        self._rag = None    # lazy-loaded on first Tier 2 request
        self._llm = None    # lazy-loaded on first Tier 2 request

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    def create_session(self) -> ChatResponse:
        cs = ChatbotSession()
        self._sessions[cs.session_id] = cs
        return ChatResponse(
            message_type="greeting",
            text=(
                "Welcome to the Secure HHPC Fault Diagnosis System.\n\n"
                "Describe the fault you are experiencing and I will guide you "
                "through a step-by-step diagnostic procedure.\n\n"
                "If your query is not covered by the structured procedures, "
                "I will automatically escalate to the AI knowledge base."
            ),
            all_procedures=self._engine.list_procedures(),
            session_id=cs.session_id,
            tier=1,
        )

    def reset_session(self, session_id: str) -> ChatResponse:
        cs = self._sessions.get(session_id)
        if not cs:
            return self._error("Session not found.", session_id)
        cs.phase = "GREET"
        cs.engine_session = None
        return ChatResponse(
            message_type="info",
            text="Session reset. Describe the new fault or select a procedure.",
            all_procedures=self._engine.list_procedures(),
            session_id=session_id,
            tier=1,
        )

    def get_session(self, session_id: str) -> Optional[ChatbotSession]:
        return self._sessions.get(session_id)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def handle_input(self, session_id: str, user_text: str) -> ChatResponse:
        cs = self._sessions.get(session_id)
        if not cs:
            return self._error("Session not found. Please refresh.", session_id)

        text = user_text.strip()

        # --- Special commands from UI buttons ---
        if text.startswith("CMD:SELECT:"):
            return self._start_procedure(cs, text.split(":", 2)[2])
        if text == "CMD:RESTART":
            if cs.engine_session:
                self._engine.restart_session(cs.engine_session)
                cs.phase = "PROCEDURE"
                return self._step_response(cs, self._engine.get_current_step(cs.engine_session))
            return self.reset_session(session_id)
        if text == "CMD:NEW":
            return self.reset_session(session_id)
        if text == "CMD:ALL_PROCS":
            return ChatResponse(
                message_type="classify_ask",
                text="Select a procedure to begin:",
                all_procedures=self._engine.list_procedures(),
                session_id=session_id,
                tier=1,
            )
        if text == "CMD:ASK_AI":
            # User explicitly escalates to Tier 2
            return ChatResponse(
                message_type="info",
                text="Please type your question and I will search the full knowledge base.",
                session_id=session_id,
                tier=2,
                show_yes_no=False,
            )
        if text.startswith("CMD:RAG:"):
            query = text[8:]
            return self._tier2_query(cs, query)

        # --- Phase routing ---
        if cs.phase in ("GREET", "DONE"):
            return self._handle_classify(cs, text)
        if cs.phase == "PROCEDURE":
            return self._handle_procedure_input(cs, text)
        if cs.phase == "RAG":
            return self._tier2_query(cs, text)

        return self._error("Unexpected state.", session_id)

    # ------------------------------------------------------------------
    # Tier 1 — Classifier → Procedure
    # ------------------------------------------------------------------
    def _handle_classify(self, cs: ChatbotSession, text: str) -> ChatResponse:
        out: ClassifierOutput = classify(text)

        if out.escalate or not out.results:
            # Low confidence -> go straight to Tier 2
            return self._tier2_query(cs, text)

        if len(out.results) == 1 or out.results[0].confidence >= 0.85:
            # High confidence single match
            return self._start_procedure(cs, out.results[0].procedure_id)

        # Multiple candidates - let user pick
        candidates = [
            {
                "id": r.procedure_id,
                "name": r.procedure_name,
                "confidence": r.confidence,
                "matched": r.matched_keywords[:4],
            }
            for r in out.results
        ]
        return ChatResponse(
            message_type="classify_ask",
            text=f"I matched your description to {len(candidates)} procedure(s). Select the most relevant:",
            candidates=candidates,
            all_procedures=self._engine.list_procedures(),
            session_id=cs.session_id,
            tier=1,
        )

    def _handle_procedure_input(self, cs: ChatbotSession, text: str) -> ChatResponse:
        answer = parse_yes_no(text)

        if answer is None:
            # Not yes/no — could be a general question, try Tier 2
            out = classify(text)
            if out.escalate or not out.results:
                # Route to Tier 2 with current question as context
                return self._tier2_query(cs, text)
            # Reclassify to different procedure
            return ChatResponse(
                message_type="classify_ask",
                text="It looks like you may be describing a different fault. Select:",
                candidates=[
                    {"id": r.procedure_id, "name": r.procedure_name,
                     "confidence": r.confidence, "matched": r.matched_keywords[:4]}
                    for r in out.results
                ],
                session_id=cs.session_id,
                tier=1,
            )

        try:
            next_step = self._engine.answer(cs.engine_session, answer)
        except (ValueError, RuntimeError) as e:
            return self._error(str(e), cs.session_id)

        return self._step_response(cs, next_step)

    def _start_procedure(self, cs: ChatbotSession, proc_id: str) -> ChatResponse:
        try:
            cs.engine_session = self._engine.start_session(proc_id)
            cs.phase = "PROCEDURE"
            first = self._engine.get_current_step(cs.engine_session)
            return self._step_response(cs, first)
        except KeyError as e:
            return self._error(str(e), cs.session_id)

    def _step_response(self, cs: ChatbotSession,
                       step: Step | DiagnosisResult) -> ChatResponse:
        if isinstance(step, DiagnosisResult):
            cs.phase = "DONE"
            return ChatResponse(
                message_type="result",
                text=f"Diagnosis complete.",
                procedure_id=step.procedure_id,
                procedure_name=step.procedure_name,
                component=step.component,
                action=step.action,
                is_ok=step.is_ok,
                session_id=cs.session_id,
                tier=1,
            )
        return ChatResponse(
            message_type="question",
            text=step.question,
            procedure_id=step.procedure_id,
            procedure_name=step.procedure_name,
            step_number=step.step_number,
            test_point=step.test_point,
            target_value=step.target_value,
            show_yes_no=True,
            session_id=cs.session_id,
            tier=1,
        )

    # ------------------------------------------------------------------
    # Tier 2 — RAG + LLM
    # ------------------------------------------------------------------
    def _tier2_query(self, cs: ChatbotSession, query: str) -> ChatResponse:
        cs.phase = "RAG"
        rag   = self._get_rag()
        llm   = self._get_llm()

        if not llm.is_available():
            return ChatResponse(
                message_type="rag_unavailable",
                text=(
                    "The AI knowledge base is not available right now.\n\n"
                    "To enable it, install Ollama and run:\n"
                    "  ollama pull phi3:mini\n"
                    "  ollama serve\n\n"
                    "Then restart the server. You can still use the structured "
                    "fault procedures above."
                ),
                all_procedures=self._engine.list_procedures(),
                session_id=cs.session_id,
                tier=2,
            )

        # Use LangChain RetrievalQA chain for the answer
        retriever = rag.get_retriever()
        result = llm.query_with_chain(question=query, retriever=retriever)

        # Also fetch chunks separately for UI source display
        chunks = rag.retrieve(query)

        if not result["success"]:
            return ChatResponse(
                message_type="error",
                text=f"AI query failed: {result['error']}",
                session_id=cs.session_id,
                tier=2,
            )

        rag_chunk_dicts = [
            {"doc": c.doc_name, "score": c.score, "preview": c.text[:120] + "..."}
            for c in chunks
        ]
        return ChatResponse(
            message_type="rag_answer",
            text=result["answer"],
            rag_chunks=rag_chunk_dicts,
            llm_latency_ms=result["latency_ms"],
            session_id=cs.session_id,
            tier=2,
            all_procedures=self._engine.list_procedures(),
        )

    # ------------------------------------------------------------------
    # Lazy loaders
    # ------------------------------------------------------------------
    def _get_rag(self):
        if self._rag is None:
            from rag_engine import RAGEngine
            self._rag = RAGEngine()
            self._rag.build_index()
        return self._rag

    def _get_llm(self):
        if self._llm is None:
            from llm import LLMManager
            self._llm = LLMManager()
        return self._llm

    def _error(self, message: str, session_id: str) -> ChatResponse:
        return ChatResponse(message_type="error", text=f"Error: {message}",
                            session_id=session_id)

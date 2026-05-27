"""
rule_engine.py  —  Tier 1
--------------------------
State-machine rule engine. Loads procedures.json and drives step-by-step
yes/no diagnosis sessions.
"""

from __future__ import annotations
import json, os
from dataclasses import dataclass, field
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_PATH = os.path.join(_HERE, "..", "data", "procedures.json")


@dataclass
class Step:
    procedure_id: str
    procedure_name: str
    state_id: str
    step_number: int
    question: str
    test_point: Optional[str]
    target_value: Optional[str]


@dataclass
class DiagnosisResult:
    procedure_id: str
    procedure_name: str
    state_id: str
    component: str
    action: str
    is_ok: bool


@dataclass
class Session:
    procedure_id: str
    current_state_id: str
    step_number: int = 0
    history: list[dict] = field(default_factory=list)
    completed: bool = False
    result: Optional[DiagnosisResult] = None


class RuleEngine:
    def __init__(self, procedures_path: str = _DATA_PATH):
        with open(procedures_path, "r", encoding="utf-8") as f:
            self._procedures: dict = json.load(f)

    def list_procedures(self) -> list[dict]:
        return [
            {"id": pid, "name": p["name"], "description": p["description"]}
            for pid, p in self._procedures.items()
        ]

    def start_session(self, procedure_id: str) -> Session:
        if procedure_id not in self._procedures:
            raise KeyError(f"Unknown procedure: {procedure_id!r}")
        return Session(
            procedure_id=procedure_id,
            current_state_id=self._procedures[procedure_id]["start"],
        )

    def get_current_step(self, session: Session) -> Step | DiagnosisResult:
        if session.completed and session.result:
            return session.result

        proc  = self._procedures[session.procedure_id]
        state = proc["states"][session.current_state_id]

        if state.get("result"):
            result = DiagnosisResult(
                procedure_id=session.procedure_id,
                procedure_name=proc["name"],
                state_id=session.current_state_id,
                component=state["component"],
                action=state["action"],
                is_ok=state.get("ok", False),
            )
            session.completed = True
            session.result = result
            return result

        session.step_number += 1
        return Step(
            procedure_id=session.procedure_id,
            procedure_name=proc["name"],
            state_id=session.current_state_id,
            step_number=session.step_number,
            question=state["question"],
            test_point=state.get("test_point"),
            target_value=state.get("target"),
        )

    def answer(self, session: Session, answer: str) -> Step | DiagnosisResult:
        answer = answer.strip().lower()
        if answer not in ("yes", "no"):
            raise ValueError(f"answer must be 'yes' or 'no', got {answer!r}")
        if session.completed:
            raise RuntimeError("Session already completed.")

        proc  = self._procedures[session.procedure_id]
        state = proc["states"][session.current_state_id]
        session.history.append({
            "state_id": session.current_state_id,
            "question": state["question"],
            "answer": answer,
        })
        session.current_state_id = state["yes"] if answer == "yes" else state["no"]
        return self.get_current_step(session)

    def restart_session(self, session: Session) -> Step | DiagnosisResult:
        proc = self._procedures[session.procedure_id]
        session.current_state_id = proc["start"]
        session.step_number = 0
        session.history.clear()
        session.completed = False
        session.result = None
        return self.get_current_step(session)

    def get_history(self, session: Session) -> list[dict]:
        return list(session.history)

"""Safe routing from source classification to bounded review steps."""

from __future__ import annotations

from dataclasses import dataclass

from .ai_provider import AIProvider, Classification


@dataclass(frozen=True)
class WorkflowPlan:
    source_kind: str
    steps: tuple[str, ...]
    needs_review: bool
    reason: str
    confidence: float

    def validate(self) -> None:
        if not self.steps:
            raise ValueError("workflow plan requires at least one step")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if any(step not in {"extract_links", "extract_text", "extract_structured_data", "visual_review", "stop_and_review", "review"} for step in self.steps):
            raise ValueError("workflow plan contains an unsupported step")


def plan_source(text: str, provider: AIProvider, url: str | None = None) -> WorkflowPlan:
    """Classify a source, then map it to a fixed safe workflow.

    Provider output influences classification only; it cannot introduce arbitrary
    actions, network destinations, or submission behavior.
    """
    return plan_classification(provider.classify(text, url))


def plan_classification(classification: Classification) -> WorkflowPlan:
    """Map an already validated classification without another provider call."""
    classification.validate()
    routes = {
        "job_alert": ("extract_links", "extract_text", "review"),
        "public_job_page": ("extract_text", "extract_structured_data", "review"),
        "image": ("visual_review",),
        "blocked": ("stop_and_review",),
        "unknown": ("review",),
    }
    steps = routes[classification.source_kind]
    # Every route ends in human review; provider confidence never removes that gate.
    plan = WorkflowPlan(classification.source_kind, steps, True, classification.reason, classification.confidence)
    plan.validate()
    return plan

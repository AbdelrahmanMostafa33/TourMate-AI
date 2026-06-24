"""
Evaluation subsystem — metrics, feasibility checks, and explainability.

Modules:
    - feasibility_checker  — Deterministic checks on itinerary feasibility
    - itinerary_metrics    — Quantitative quality metrics for generated itineraries
    - agent_metrics        — Performance tracking across AI agent calls
    - explainability       — Human-readable explanations of agent decisions
"""

from ai_engine.evaluation.agent_metrics import agent_metrics, AgentMetricsCollector
from ai_engine.evaluation.explainability import (
    explain_validation_decision,
    explain_metric_scores,
    explain_stop_placement,
    explain_preference_change,
    explain_profile,
    format_full_explanation,
    quick_summary,
)
from ai_engine.evaluation.feasibility_checker import run_programmatic_checks
from ai_engine.evaluation.itinerary_metrics import (
    score_category_diversity,
    score_interest_alignment,
    score_pacing,
    score_geographic_coverage,
    compute_all_metrics,
)

__all__ = [
    "agent_metrics",
    "AgentMetricsCollector",
    "explain_validation_decision",
    "explain_metric_scores",
    "explain_stop_placement",
    "explain_preference_change",
    "explain_profile",
    "format_full_explanation",
    "quick_summary",
    "run_programmatic_checks",
    "score_category_diversity",
    "score_interest_alignment",
    "score_pacing",
    "score_geographic_coverage",
    "compute_all_metrics",
]

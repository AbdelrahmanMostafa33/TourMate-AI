"""
Production Metrics Collection for TourMate AI.

Provides structured metrics collection for monitoring agent performance,
error rates, and latency in production environments.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class AgentMetrics:
    """Metrics for a single agent execution."""
    agent_name: str
    duration_ms: float
    success: bool
    error_message: Optional[str] = None
    token_usage: Optional[Dict[str, int]] = None
    timestamp: float = field(default_factory=time.time)


class MetricsCollector:
    """Collects and aggregates metrics across agent executions."""
    
    def __init__(self) -> None:
        self._metrics: List[AgentMetrics] = []
        self._by_agent: Dict[str, List[AgentMetrics]] = defaultdict(list)
    
    def record(self, metrics: AgentMetrics) -> None:
        """Record a single agent execution metric."""
        self._metrics.append(metrics)
        self._by_agent[metrics.agent_name].append(metrics)
        
        # Log individual execution for production monitoring
        status = "✓" if metrics.success else "✗"
        token_info = ""
        if metrics.token_usage:
            total = metrics.token_usage.get("total_tokens", 0)
            token_info = f" | {total} tokens"
        
        logger.info(
            "[Metrics] %s %s — %.0fms%s%s",
            status, metrics.agent_name, metrics.duration_ms, token_info,
            f" | {metrics.error_message}" if metrics.error_message else ""
        )
    
    def get_agent_summary(self, agent_name: str) -> Dict:
        """Get summary statistics for a specific agent."""
        metrics = self._by_agent.get(agent_name, [])
        if not metrics:
            return {}
        
        successful = [m for m in metrics if m.success]
        failed = [m for m in metrics if not m.success]
        
        durations = [m.duration_ms for m in successful]
        avg_duration = sum(durations) / len(durations) if durations else 0
        p95_duration = sorted(durations)[int(len(durations) * 0.95)] if durations else 0
        
        total_tokens = sum(
            m.token_usage.get("total_tokens", 0) 
            for m in metrics 
            if m.token_usage
        )
        
        return {
            "agent": agent_name,
            "total_calls": len(metrics),
            "successful_calls": len(successful),
            "failed_calls": len(failed),
            "error_rate": len(failed) / len(metrics) if metrics else 0,
            "avg_duration_ms": avg_duration,
            "p95_duration_ms": p95_duration,
            "total_tokens": total_tokens,
        }
    
    def get_global_summary(self) -> Dict:
        """Get summary statistics across all agents."""
        if not self._metrics:
            return {}
        
        summaries = {
            agent: self.get_agent_summary(agent)
            for agent in self._by_agent.keys()
        }
        
        total_calls = len(self._metrics)
        total_successful = sum(s["successful_calls"] for s in summaries.values())
        total_failed = sum(s["failed_calls"] for s in summaries.values())
        total_tokens = sum(s["total_tokens"] for s in summaries.values())
        
        return {
            "total_calls": total_calls,
            "successful_calls": total_successful,
            "failed_calls": total_failed,
            "overall_error_rate": total_failed / total_calls if total_calls else 0,
            "total_tokens": total_tokens,
            "by_agent": summaries,
        }
    
    def print_summary(self) -> None:
        """Print a formatted summary of all metrics."""
        summary = self.get_global_summary()
        if not summary:
            print("\n[Metrics] No metrics recorded.")
            return
        
        print(f"\n{'='*70}")
        print(f"  Production Metrics Summary")
        print(f"{'='*70}")
        print(f"  Total Calls: {summary['total_calls']}")
        print(f"  Successful: {summary['successful_calls']} ({(summary['successful_calls']/summary['total_calls']*100):.1f}%)")
        print(f"  Failed: {summary['failed_calls']} ({(summary['overall_error_rate']*100):.1f}%)")
        print(f"  Total Tokens: {summary['total_tokens']:,}")
        print(f"\n  {'Agent':<20} {'Calls':>6} {'Err%':>5} {'Avg(ms)':>8} {'P95(ms)':>8} {'Tokens':>10}")
        print(f"  {'-'*20} {'-'*6} {'-'*5} {'-'*8} {'-'*8} {'-'*10}")
        
        for agent_name, agent_summary in sorted(summary["by_agent"].items()):
            print(
                f"  {agent_name:<20} "
                f"{agent_summary['total_calls']:>6} "
                f"{agent_summary['error_rate']*100:>4.1f}% "
                f"{agent_summary['avg_duration_ms']:>7.0f} "
                f"{agent_summary['p95_duration_ms']:>7.0f} "
                f"{agent_summary['total_tokens']:>10,}"
            )
        print(f"{'='*70}\n")
    
    def reset(self) -> None:
        """Clear all recorded metrics."""
        self._metrics.clear()
        self._by_agent.clear()


# Singleton metrics collector
metrics_collector = MetricsCollector()


def record_agent_execution(
    agent_name: str,
    duration_ms: float,
    success: bool,
    error_message: Optional[str] = None,
    token_usage: Optional[Dict[str, int]] = None,
) -> None:
    """Convenience function to record agent execution metrics."""
    metrics = AgentMetrics(
        agent_name=agent_name,
        duration_ms=duration_ms,
        success=success,
        error_message=error_message,
        token_usage=token_usage,
    )
    metrics_collector.record(metrics)

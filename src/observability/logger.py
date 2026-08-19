"""
Observability Module — Structured Logging, Metrics, and Tracing

Provides enterprise-grade observability for the migration pipeline:
1. Structured JSON logging with correlation IDs
2. Metrics collection (Prometheus-compatible)
3. OpenTelemetry-compatible tracing spans
4. Real-time dashboard data emission
"""
import json
import logging
import time
import uuid
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from contextlib import contextmanager


@dataclass
class Span:
    """Represents a tracing span for a migration operation."""
    span_id: str
    operation: str
    started_at: float
    ended_at: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "running"
    attributes: Dict[str, Any] = field(default_factory=dict)
    children: list = field(default_factory=list)

    def end(self, status: str = "ok"):
        self.ended_at = time.time()
        self.duration_ms = (self.ended_at - self.started_at) * 1000
        self.status = status


@dataclass
class MetricsCollector:
    """Collects pipeline metrics in Prometheus-compatible format."""
    counters: Dict[str, float] = field(default_factory=dict)
    gauges: Dict[str, float] = field(default_factory=dict)
    histograms: Dict[str, list] = field(default_factory=dict)

    def increment(self, name: str, value: float = 1.0, labels: Optional[Dict] = None):
        key = self._key(name, labels)
        self.counters[key] = self.counters.get(key, 0) + value

    def set_gauge(self, name: str, value: float, labels: Optional[Dict] = None):
        key = self._key(name, labels)
        self.gauges[key] = value

    def observe(self, name: str, value: float, labels: Optional[Dict] = None):
        key = self._key(name, labels)
        if key not in self.histograms:
            self.histograms[key] = []
        self.histograms[key].append(value)

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = []
        for name, value in self.counters.items():
            lines.append(f"# TYPE {name} counter\n{name} {value}")
        for name, value in self.gauges.items():
            lines.append(f"# TYPE {name} gauge\n{name} {value}")
        for name, values in self.histograms.items():
            avg = sum(values) / len(values) if values else 0
            lines.append(f"# TYPE {name} histogram\n{name}_count {len(values)}\n{name}_avg {avg:.2f}")
        return "\n".join(lines)

    @staticmethod
    def _key(name: str, labels: Optional[Dict]) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


class MigrationLogger:
    """
    Structured JSON logger with correlation ID tracking.
    """

    def __init__(self, run_id: Optional[str] = None):
        self.run_id = run_id or str(uuid.uuid4())[:8]
        self.metrics = MetricsCollector()
        self._spans: list = []
        self._logger = logging.getLogger("refactor-engine")
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(message)s'))
        self._logger.addHandler(handler)
        self._logger.setLevel(logging.INFO)

    def info(self, message: str, **kwargs):
        self._log("INFO", message, **kwargs)

    def warn(self, message: str, **kwargs):
        self._log("WARN", message, **kwargs)

    def error(self, message: str, **kwargs):
        self._log("ERROR", message, **kwargs)

    def _log(self, level: str, message: str, **kwargs):
        entry = {
            "timestamp": time.time(),
            "level": level,
            "run_id": self.run_id,
            "message": message,
            **kwargs,
        }
        self._logger.info(json.dumps(entry))

    @contextmanager
    def span(self, operation: str, **attributes):
        """Create a tracing span as a context manager."""
        s = Span(
            span_id=str(uuid.uuid4())[:8],
            operation=operation,
            started_at=time.time(),
            attributes=attributes,
        )
        self._spans.append(s)
        self.info(f"Span started: {operation}", span_id=s.span_id)
        try:
            yield s
            s.end("ok")
            self.metrics.observe("span_duration_ms", s.duration_ms or 0, {"operation": operation})
            self.info(f"Span completed: {operation}", span_id=s.span_id, duration_ms=s.duration_ms)
        except Exception as e:
            s.end("error")
            self.error(f"Span failed: {operation}", span_id=s.span_id, error=str(e))
            raise

    def get_trace(self) -> list:
        """Return all spans for this migration run."""
        return [
            {
                "span_id": s.span_id,
                "operation": s.operation,
                "duration_ms": s.duration_ms,
                "status": s.status,
                "attributes": s.attributes,
            }
            for s in self._spans
        ]

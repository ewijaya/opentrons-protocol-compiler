"""Resource reporting: tip/step/volume/time metrics and the naive-vs-optimized table."""

from pipettec.report.metrics import (
    Metrics,
    compute_metrics,
    format_comparison_markdown,
    format_report,
)

__all__ = ["Metrics", "compute_metrics", "format_report", "format_comparison_markdown"]

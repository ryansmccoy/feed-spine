"""
Observation data conversion mixin.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any


def _enum_val(obj: Any) -> str | None:
    """Return .value if obj is an enum, else str(obj). None passthrough."""
    if obj is None:
        return None
    return obj.value if hasattr(obj, "value") else str(obj)


def _canonical_key(obj: Any) -> str:
    """Return .canonical_key if present, else str(obj)."""
    return obj.canonical_key if hasattr(obj, "canonical_key") else str(obj)


def _generate_observation_key(obs: Any) -> str:
    """Build a deterministic key from observation components."""
    if hasattr(obs, "observation_key"):
        return obs.observation_key

    parts = [
        obs.entity_id,
        _canonical_key(obs.metric),
        _canonical_key(obs.period),
        obs.as_of.isoformat() if obs.as_of else "na",
    ]
    if hasattr(obs, "provenance_ref") and obs.provenance_ref:
        parts.append(obs.provenance_ref.external_id)

    return sha256("|".join(parts).encode()).hexdigest()[:32]


class ObservationConverterMixin:
    """Mixin for observation data conversion."""

    def _observation_to_dict(self, obs: Any) -> dict[str, Any]:
        """Convert Observation dataclass to storage dict."""
        obs_key = _generate_observation_key(obs)

        return {
            "observation_id": getattr(obs, "observation_id", str(uuid.uuid4())),
            "observation_key": obs_key,
            "entity_id": obs.entity_id,
            "security_id": getattr(obs, "security_id", None),
            "metric_key": _canonical_key(obs.metric),
            "period_key": _canonical_key(obs.period),
            "observation_type": _enum_val(obs.observation_type),
            "value_normalized": float(obs.value.value_normalized),
            "value_raw": float(obs.value.value_raw),
            "value_unit": obs.value.unit,
            "value_scale": obs.value.scale,
            "value_currency": obs.value.currency,
            "value_string": getattr(obs, "value_string", None),
            "fiscal_year": obs.period.fiscal_year,
            "fiscal_quarter": getattr(obs.period, "quarter", None),
            "period_type": _enum_val(obs.period.period_type),
            "period_start": getattr(obs.period, "period_start", None),
            "period_end": getattr(obs.period, "period_end", None),
            "as_of": obs.as_of,
            "captured_at": getattr(obs, "captured_at", datetime.now(UTC)),
            "provenance_kind": _enum_val(obs.provenance_ref.kind) if obs.provenance_ref else None,
            "provenance_external_id": obs.provenance_ref.external_id if obs.provenance_ref else None,
            "source_vendor": _enum_val(obs.source_key.vendor) if obs.source_key and obs.source_key.vendor else None,
            "source_dataset": obs.source_key.dataset if obs.source_key else None,
            "source_field": obs.source_key.field_name if obs.source_key else None,
            "estimate_scope": _enum_val(obs.estimate_info.scope) if obs.estimate_info else None,
            "estimator": obs.estimate_info.estimator if obs.estimate_info else None,
            "num_estimates": obs.estimate_info.num_estimates if obs.estimate_info else None,
            "high_estimate": float(obs.estimate_info.high_estimate)
            if obs.estimate_info and obs.estimate_info.high_estimate
            else None,
            "low_estimate": float(obs.estimate_info.low_estimate)
            if obs.estimate_info and obs.estimate_info.low_estimate
            else None,
            "supersedes_id": getattr(obs, "supersedes_id", None),
            "is_superseded": getattr(obs, "superseded_by_id", None) is not None,
            "confidence": getattr(obs, "confidence", 1.0),
            "content": json.dumps(
                {
                    "raw_value": getattr(obs, "raw_value", None),
                    "notes": getattr(obs, "notes", None),
                }
            ),
        }

"""Record validation. Runs in the core, after the adapter, for every source.

Adapters may do their own source-specific checks, but they cannot skip these.
"""

from __future__ import annotations

from datetime import UTC

from .countries import is_valid_country_code, region_problem
from .errors import RecordRejected
from .record import CanonicalRecord


def collect_problems(
    record: CanonicalRecord, allowed_countries: frozenset[str] | None = None
) -> list[str]:
    problems: list[str] = []
    m = record.metadata

    if not is_valid_country_code(m.country_code):
        problems.append(
            f"country_code {m.country_code!r} is not an ISO 3166-1 alpha-2 code"
        )
    elif allowed_countries is not None and m.country_code not in allowed_countries:
        problems.append(
            f"country_code {m.country_code!r} is outside this source's scope "
            f"{sorted(allowed_countries)}"
        )
    else:
        reason = region_problem(m.country_code, m.region_code)
        if reason:
            problems.append(reason)

    if not m.source_id:
        problems.append("source_id is empty")
    if not record.record_key:
        problems.append("record_key is empty")

    if m.fetched_at.tzinfo is None:
        problems.append("fetched_at must be timezone-aware")
    elif m.source_date > m.fetched_at.astimezone(UTC).date():
        problems.append(
            f"source_date {m.source_date} is after fetched_at {m.fetched_at.date()}"
        )

    if not isinstance(record.attributes, dict):
        problems.append("attributes must be a mapping")

    return problems


def validate(
    record: CanonicalRecord, allowed_countries: frozenset[str] | None = None
) -> CanonicalRecord:
    problems = collect_problems(record, allowed_countries)
    if problems:
        raise RecordRejected(problems)
    return record

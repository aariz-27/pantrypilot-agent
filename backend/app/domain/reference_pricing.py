"""Median reference-price computation (M10 policy, DEC-013).

For each (canonical_id, normalized_unit) group of valid contributors:
- one contributor -> that value;
- odd count -> the middle value;
- even count -> the arithmetic mean of the two middle values (standard
  median math over already-compatible values -- not the "averaging
  incompatible variants" DEC-013 forbids, since every contributor in
  the group already shares the same canonical_id and normalized_unit).

Contributors sharing one canonical_id but differing normalized_unit
are never combined into one statistic; if a canonical_id has more than
one normalized_unit represented, every group is reported as an
IncompatibleUnitGroup data-quality signal and none of them is silently
promoted -- the caller decides whether to promote the largest/most
common group or flag it for manual review.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import median

from app.domain.grocery_models import (
    IncompatibleUnitGroup,
    ReferencePriceCandidate,
    ReferencePriceResult,
)


def compute_reference_prices(
    candidates_by_canonical_unit: dict[tuple[str, str], list[ReferencePriceCandidate]],
) -> tuple[list[ReferencePriceResult], list[IncompatibleUnitGroup]]:
    """Input is already grouped by (canonical_id, normalized_unit).
    Detects canonical IDs spanning more than one normalized_unit and
    reports them separately rather than silently merging or picking one."""

    by_canonical: dict[str, list[str]] = defaultdict(list)
    for canonical_id, unit in candidates_by_canonical_unit:
        by_canonical[canonical_id].append(unit)

    incompatible: list[IncompatibleUnitGroup] = []
    incompatible_canonical_ids: set[str] = set()
    for canonical_id, units in by_canonical.items():
        distinct_units = set(units)
        if len(distinct_units) > 1:
            incompatible_canonical_ids.add(canonical_id)
            total_contributors = sum(
                len(candidates_by_canonical_unit[(canonical_id, u)]) for u in distinct_units
            )
            incompatible.append(
                IncompatibleUnitGroup(
                    canonical_id=canonical_id,
                    units_found=tuple(sorted(distinct_units)),
                    contributor_count=total_contributors,
                )
            )

    results: list[ReferencePriceResult] = []
    for (canonical_id, unit), candidates in candidates_by_canonical_unit.items():
        if canonical_id in incompatible_canonical_ids:
            continue
        if not candidates:
            continue

        prices = sorted(c.normalized_price_per_unit for c in candidates)
        contributor_count = len(prices)
        median_price = median(prices)

        if contributor_count == 1:
            basis = "median_single"
        elif contributor_count % 2 == 1:
            basis = "median_odd"
        else:
            basis = "median_even"

        # Provenance: the contributor whose price is closest to the
        # computed median (ties broken by source name for determinism).
        representative = min(
            candidates,
            key=lambda c: (abs(c.normalized_price_per_unit - median_price), c.source_name),
        )

        results.append(
            ReferencePriceResult(
                canonical_id=canonical_id,
                normalized_unit=unit,
                normalized_price_per_unit=round(median_price, 4),
                contributor_count=contributor_count,
                aggregation_basis=basis,
                source_name=representative.source_name,
                source_product_name=representative.source_product_name,
                source_url=representative.source_url,
                package_quantity=representative.package_quantity,
                package_unit=representative.package_unit,
                package_price_aed=representative.package_price_aed,
                normalized_package_quantity=representative.normalized_package_quantity,
            )
        )

    return results, incompatible

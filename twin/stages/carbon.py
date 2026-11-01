"""Thomas-style carbon breakthrough and oxidation coupling."""

from twin.physics import thomas_breakthrough_fraction


def breakthrough(cumulative_capacity_fraction: float, steepness: float = 22.0) -> float:
    """Thomas logistic in normalized loading; at 0.9 capacity with k=22, C/C0≈0.10."""
    return thomas_breakthrough_fraction(cumulative_capacity_fraction, 1.0, steepness)


def oxidized_salt_passage(
    base_b_lmh: float, chlorine_exposure_fraction: float, coupling: float = 0.7
) -> float:
    """Irreversible salt-passage proxy; B=1.3 and exposure=1 gives 2.21 LMH."""
    return max(0.0, base_b_lmh * (1 + coupling * max(0.0, chlorine_exposure_fraction)))

"""Ultrafiltration cake resistance and partial flush recovery."""


def resistance_after_flush(resistance_per_m: float, reversible_fraction: float) -> float:
    """A flush removes its reversible fraction; 10e10 at 50% leaves 5e10 m⁻¹."""
    if resistance_per_m < 0 or not 0 <= reversible_fraction <= 1:
        raise ValueError("resistance must be nonnegative and recovery fraction in [0,1]")
    return resistance_per_m * (1 - reversible_fraction)


def advance_resistance(resistance_per_m: float, daily_growth: float, days: float = 1) -> float:
    """Monotone unflushed growth; 1e10 plus 1e8/day for two days is 1.02e10."""
    if resistance_per_m < 0 or daily_growth < 0 or days < 0:
        raise ValueError("resistance, growth, and time must be nonnegative")
    return resistance_per_m + daily_growth * days

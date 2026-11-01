"""Household usage primitives."""


def household_daily_demand_l(household_size: int, litres_per_person_day: float = 2.6) -> float:
    """Base demand scales by household size; 4 people at 2.6 L/day use 10.4 L/day."""
    if household_size < 1 or litres_per_person_day < 0:
        raise ValueError("household size must be positive and demand nonnegative")
    return household_size * litres_per_person_day


def uv_intensity_fraction(hours_used: float, rated_hours: float, initial: float = 1.0) -> float:
    """Linear usage-only lamp decay; 3000 h of 10000 h leaves 70% at initial=1."""
    if rated_hours <= 0 or hours_used < 0:
        raise ValueError("rated hours must be positive and use nonnegative")
    return max(0.0, initial * (1 - hours_used / rated_hours))


def alkaliser_capacity_fraction(
    volume_l: float, rated_litres: float, initial: float = 1.0
) -> float:
    """Linear volume-only depletion; 7500 L of a 10000 L capacity leaves 25%."""
    if rated_litres <= 0 or volume_l < 0:
        raise ValueError("rated litres must be positive and use nonnegative")
    return max(0.0, initial * (1 - volume_l / rated_litres))

"""Lumped storage tank draw/refill helpers."""


def fill_time_hours(draw_litres: float, production_l_h: float) -> float:
    """Fill duration is volume/production; 20 L at 10 L/h takes 2 h."""
    if draw_litres < 0 or production_l_h <= 0:
        raise ValueError("draw must be nonnegative and production positive")
    return draw_litres / production_l_h


def tank_after_draw(level_l: float, draw_litres: float, capacity_l: float) -> float:
    """Clip a draw to available water; a 5 L draw from a 4 L tank leaves zero."""
    if capacity_l < 0 or level_l < 0 or draw_litres < 0:
        raise ValueError("tank volumes must be nonnegative")
    return min(capacity_l, max(0.0, level_l) - min(max(0.0, level_l), draw_litres))

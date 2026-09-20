"""METAR true direction and runway magnetic heading must share a reference."""
import math
from .config import Settings
from .models import WindComponents

def angle_difference(direction: float, heading: float) -> float:
    return (direction - heading + 180) % 360 - 180

def components(direction: float, heading: float, speed: float, name: str) -> WindComponents:
    angle = math.radians(angle_difference(direction, heading))
    return WindComponents(name, speed * math.cos(angle), speed * abs(math.sin(angle)))

def calculate_runways(direction: float | None, speed: float, variable: bool,
                      settings: Settings) -> tuple[WindComponents, ...]:
    if speed == 0:
        return tuple(WindComponents(r.name, 0, 0) for r in settings.runways)
    if variable:
        return tuple(WindComponents(r.name, None, speed) for r in settings.runways)
    if direction is None or settings.magnetic_variation_deg is None:
        raise ValueError('Set verified MAGNETIC_VARIATION_DEG to compare true METAR winds with magnetic runways.')
    return tuple(components(direction, (r.magnetic_heading + settings.magnetic_variation_deg) % 360,
                            speed, r.name) for r in settings.runways)

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

class Status(StrEnum):
    PASS = 'PASS'
    FAIL = 'FAIL'
    UNKNOWN = 'UNKNOWN'

@dataclass
class WeatherObservation:
    airport: str
    raw_metar: str = ''
    observation_time: datetime | None = None
    flight_category: str | None = None
    visibility_sm: float | None = None
    visibility_is_lower_bound: bool = False
    ceiling_ft: float | None = None
    wind_direction: float | None = None
    wind_speed_kt: float | None = None
    wind_gust_kt: float | None = None
    is_variable_wind: bool = False
    issues: list[str] = field(default_factory=list)

@dataclass(frozen=True)
class WindComponents:
    runway: str
    headwind_kt: float | None
    crosswind_kt: float

@dataclass
class WeatherEvaluation:
    status: Status = Status.UNKNOWN
    visibility_pass: bool | None = None
    ceiling_pass: bool | None = None
    wind_pass: bool | None = None
    crosswind_pass: bool | None = None
    flight_category_pass: bool | None = None
    selected_runway: str | None = None
    crosswind_kt: float | None = None
    headwind_kt: float | None = None
    worst_wind_kt: float | None = None
    runway_components: tuple[WindComponents, ...] = ()
    failure_reasons: list[str] = field(default_factory=list)
    unknown_reasons: list[str] = field(default_factory=list)

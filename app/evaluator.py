from datetime import datetime, timezone
import logging
import math
from .config import Settings
from .models import WeatherObservation, WeatherEvaluation, Status
from .runway import calculate_runways

log = logging.getLogger(__name__)

def evaluate(w: WeatherObservation, settings: Settings, now: datetime | None = None) -> WeatherEvaluation:
    e = WeatherEvaluation(unknown_reasons=list(w.issues))
    m = settings.minimums
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Evaluation clock must be timezone-aware')
    if w.airport != settings.airport:
        e.unknown_reasons.append('Airport mismatch.')
    if w.observation_time is None or w.observation_time.tzinfo is None:
        e.unknown_reasons.append('Observation timestamp is missing or has no timezone.')
    else:
        age = (now - w.observation_time).total_seconds() / 60
        log.info('METAR observed at %s', w.observation_time.isoformat())
        if age < 0:
            e.unknown_reasons.append('METAR observation is in the future.')
        elif age > m.max_age_minutes:
            e.unknown_reasons.append(f'METAR is stale: {age:.1f} minutes old (maximum {m.max_age_minutes:g}).')
    if not w.raw_metar:
        e.unknown_reasons.append('Raw METAR is missing.')
    for label, value in [('Visibility', w.visibility_sm), ('Wind speed', w.wind_speed_kt)]:
        if value is None or not math.isfinite(value) or value < 0:
            e.unknown_reasons.append(f'{label} is missing or invalid.')
    if w.wind_gust_kt is not None and (not math.isfinite(w.wind_gust_kt) or w.wind_gust_kt < 0):
        e.unknown_reasons.append('Wind gust is invalid.')
    if w.ceiling_ft is not None and (not math.isfinite(w.ceiling_ft) or w.ceiling_ft < 0):
        e.unknown_reasons.append('Ceiling is invalid.')
    if w.flight_category not in ('VFR', 'MVFR', 'IFR', 'LIFR'):
        e.unknown_reasons.append('Flight category is missing or invalid.')
    if not w.is_variable_wind and w.wind_speed_kt and (w.wind_direction is None or not math.isfinite(w.wind_direction) or not 0 <= w.wind_direction <= 360):
        e.unknown_reasons.append('Wind direction is missing or invalid.')
    if w.visibility_is_lower_bound and w.visibility_sm is not None and w.visibility_sm < m.visibility_sm:
        e.unknown_reasons.append('Reported visibility lower bound is below the configured minimum; actual visibility is uncertain.')
    if e.unknown_reasons:
        log.info('Evaluation UNKNOWN: %s', e.unknown_reasons)
        return e
    e.visibility_pass = w.visibility_sm >= m.visibility_sm
    e.ceiling_pass = w.ceiling_ft is None or w.ceiling_ft >= m.ceiling_ft
    e.flight_category_pass = w.flight_category == m.flight_category
    e.worst_wind_kt = max(w.wind_speed_kt, w.wind_gust_kt or 0)
    e.wind_pass = e.worst_wind_kt <= m.max_wind_kt
    try:
        e.runway_components = calculate_runways(w.wind_direction, w.wind_speed_kt, w.is_variable_wind, settings)
    except ValueError as exc:
        e.unknown_reasons.append(str(exc))
        log.info('Evaluation UNKNOWN: %s', e.unknown_reasons)
        return e
    best = max(e.runway_components, key=lambda c: c.headwind_kt if c.headwind_kt is not None else 0)
    e.selected_runway = best.runway if not w.is_variable_wind or e.worst_wind_kt == 0 else None
    e.crosswind_kt, e.headwind_kt = best.crosswind_kt, best.headwind_kt
    e.crosswind_pass = best.crosswind_kt <= m.max_crosswind_kt or math.isclose(best.crosswind_kt, m.max_crosswind_kt, rel_tol=0, abs_tol=1e-9)
    if not e.visibility_pass:
        e.failure_reasons.append(f'Visibility {w.visibility_sm:g} SM is below your {m.visibility_sm:g} SM minimum.')
    if not e.ceiling_pass:
        e.failure_reasons.append(f'Ceiling {w.ceiling_ft:,.0f} ft is below your {m.ceiling_ft:,.0f} ft minimum.')
    if not e.wind_pass:
        kind = 'Wind gust' if w.wind_gust_kt is not None and w.wind_gust_kt >= w.wind_speed_kt else 'Wind'
        e.failure_reasons.append(f'{kind} {e.worst_wind_kt:g} kt exceeds your {m.max_wind_kt:g} kt maximum.')
    if not e.crosswind_pass:
        e.failure_reasons.append(f'Crosswind {e.crosswind_kt:.1f} kt exceeds your {m.max_crosswind_kt:g} kt maximum.')
    if not e.flight_category_pass:
        e.failure_reasons.append(f'Flight category is {w.flight_category}.')
    e.status = Status.FAIL if e.failure_reasons else Status.PASS
    log.info('Evaluation %s: %s', e.status, e.failure_reasons)
    return e

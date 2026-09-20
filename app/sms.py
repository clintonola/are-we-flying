from datetime import datetime, timezone
import re
from .config import Settings
from .models import Status, WeatherEvaluation, WeatherObservation

DISCLAIMER = 'Weather check only. Verify official weather before flight.'
HELP = "ARE WE FLYING?\nCheck current weather against my personal minimums.\n\nMETAR\nShow the latest raw {airport} METAR.\n\nLIMITS\nShow my configured personal minimums.\n\nHELP\nShow commands."
UNKNOWN_COMMAND = "I don't recognize that command.\n\nTry:\nARE WE FLYING?\nMETAR\nLIMITS\nHELP"

def command(body: str) -> str:
    return ' '.join(re.sub(r'[^\w\s]', ' ', body.upper()).split())

def unknown(reason: str, raw: str = '') -> str:
    return ('🟡 WEATHER CHECK NEEDED\n\nUnable to make a reliable determination.\n\nReason:\n'
            + reason + (f'\n\nMETAR:\n{raw}' if raw else '') + '\n\nVerify official weather before flight.')

def wind_text(w: WeatherObservation) -> str:
    if w.wind_speed_kt == 0 and not w.wind_gust_kt:
        return 'Calm'
    direction = 'Variable' if w.is_variable_wind else f'{w.wind_direction:g}° true'
    gust = f'G{w.wind_gust_kt:g}' if w.wind_gust_kt is not None else ''
    return f'{direction} @ {w.wind_speed_kt:g}{gust} kt'

def format_evaluation(w: WeatherObservation, e: WeatherEvaluation) -> str:
    if e.status == Status.UNKNOWN:
        return unknown('\n'.join(dict.fromkeys(e.unknown_reasons)), w.raw_metar)
    mark = lambda passed: '✅' if passed else '❌'
    good = e.status == Status.PASS
    ceiling = f'{w.ceiling_ft:,.0f} ft' if w.ceiling_ft is not None else 'No ceiling reported'
    return '\n'.join([
        "🟢 WE'RE FLYING" if good else "🔴 WE'RE NOT FLYING", '',
        f'{w.airport} is {"within" if good else "outside"} your personal minimums.', '',
        f'{w.flight_category} {mark(e.flight_category_pass)}',
        f'Visibility: {w.visibility_sm:g} SM {mark(e.visibility_pass)}',
        f'Ceiling: {ceiling} {mark(e.ceiling_pass)}',
        f'Wind: {wind_text(w)} {mark(e.wind_pass)}',
        f'Best runway: {e.selected_runway or "Undetermined (variable wind)"}',
        f'Crosswind: {e.crosswind_kt:.1f} kt {mark(e.crosswind_pass)}' + (' (conservative)' if w.is_variable_wind else ''),
        f'Max wind: {e.worst_wind_kt:g} kt {mark(e.wind_pass)}', '',
        'All personal minimums met.' if good else 'FAILED:\n' + '\n'.join('• ' + r for r in e.failure_reasons),
        '', 'METAR:', w.raw_metar, '', DISCLAIMER])

def format_metar(w: WeatherObservation, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    if not w.raw_metar or w.observation_time is None:
        return unknown('Raw METAR or observation timestamp is unavailable.', w.raw_metar)
    age = (now - w.observation_time).total_seconds() / 60
    return f'{w.airport} METAR\n\n{w.raw_metar}\n\nObserved:\n{w.observation_time.isoformat()}\n\nAge:\n{age:.1f} minutes\n\nRaw report only; freshness and minimums have not been evaluated.'

def format_limits(s: Settings) -> str:
    m = s.minimums
    return (f'MY PERSONAL MINIMUMS\n\nVisibility: >= {m.visibility_sm:g} SM\n'
            f'Ceiling: >= {m.ceiling_ft:,.0f} ft\nMax wind/gust: <= {m.max_wind_kt:g} kt\n'
            f'Max crosswind: <= {m.max_crosswind_kt:g} kt\nFlight category: {m.flight_category}')

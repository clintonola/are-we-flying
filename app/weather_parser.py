"""Strict normalization of AWC JSON, checked against critical raw METAR tokens."""
from datetime import datetime, timezone
from fractions import Fraction
import math
import re
from .models import WeatherObservation

def number(value: object) -> float:
    if isinstance(value, bool) or value is None:
        raise ValueError('missing numeric value')
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError('invalid numeric value')
    return result

def visibility(value: object) -> float:
    if isinstance(value, str):
        text = value.strip().upper()
        # Plus/P denotes a lower bound: use it conservatively. Less-than is unknown.
        if text.startswith(('M', '<')):
            raise ValueError('less-than visibility requires review')
        text = text.removesuffix('SM').strip().removeprefix('P').removesuffix('+')
        if not re.fullmatch(r'\d+(?:\.\d+)?|\d+/\d+|\d+ \d+/\d+', text):
            raise ValueError('unrecognized visibility')
        return number(sum(float(Fraction(p)) for p in text.split()))
    return number(value)

def timestamp(value: object) -> datetime:
    if isinstance(value, bool) or value is None:
        raise ValueError('missing timestamp')
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(number(value), timezone.utc)
    result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('timestamp has no timezone')
    return result.astimezone(timezone.utc)

def parse_weather(data: dict, airport: str) -> WeatherObservation:
    w = WeatherObservation(airport=airport)
    raw = data.get('rawOb')
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 1200:
        w.issues.append('Raw METAR is missing or malformed.')
    else:
        w.raw_metar = raw.strip()
    body = w.raw_metar.split(' RMK')[0]
    tokens = body.split()
    station_index = 1 if tokens and tokens[0] in ('METAR', 'SPECI') else 0
    if data.get('icaoId') != airport or len(tokens) <= station_index or tokens[station_index] != airport:
        w.issues.append('METAR airport does not match the configured airport.')
    try:
        w.observation_time = timestamp(data.get('obsTime'))
        report_times = [t for t in tokens if re.fullmatch(r'\d{6}Z', t)]
        if report_times != [w.observation_time.strftime('%d%H%MZ')]:
            raise ValueError('raw and structured observation time disagree')
    except (ValueError, TypeError, OverflowError, OSError):
        w.issues.append('Observation timestamp is missing or malformed.')
    w.flight_category = data.get('fltCat')
    if w.flight_category not in ('VFR', 'MVFR', 'IFR', 'LIFR'):
        w.issues.append('Flight category is missing or unrecognized.')
    try:
        w.visibility_sm = visibility(data.get('visib'))
        raw_visibility = re.search(r'(?<!\S)((?:\d+ )?P?\d+(?:/\d+|\.\d+)?)SM(?:\s|$)', body)
        w.visibility_is_lower_bound = '+' in str(data.get('visib')) or 'P' in str(data.get('visib')) or (raw_visibility is not None and 'P' in raw_visibility[1])
        if raw_visibility is None or visibility(raw_visibility[1]) != w.visibility_sm:
            raise ValueError('raw and structured visibility disagree')
    except (ValueError, TypeError, ZeroDivisionError, OverflowError):
        w.issues.append('Visibility is missing or cannot be reliably interpreted.')
    try:
        clouds = data.get('clouds')
        if not isinstance(clouds, list):
            raise ValueError()
        ceilings = []
        for cloud in clouds:
            if not isinstance(cloud, dict):
                raise ValueError()
            cover = cloud.get('cover')
            if cover not in ('BKN', 'OVC', 'VV', 'OVX', 'FEW', 'SCT', 'CLR', 'SKC', 'NSC', 'NCD', 'CAVOK'):
                raise ValueError()
            if cover in ('BKN', 'OVC', 'VV', 'OVX'):
                ceilings.append(number(cloud.get('base')))
        raw_ceilings = []
        sky_tokens = [t for t in tokens if t.startswith(('BKN', 'OVC', 'VV', 'FEW', 'SCT')) or t in ('CLR', 'SKC', 'NSC', 'NCD', 'CAVOK')]
        if not sky_tokens:
            raise ValueError()
        for token in sky_tokens:
            if token.startswith(('FEW', 'SCT')) and not re.fullmatch(r'(?:FEW|SCT)\d{3}(?:CB|TCU)?', token):
                raise ValueError()
        for token in tokens:
            if token.startswith(('BKN', 'OVC', 'VV')):
                match = re.fullmatch(r'(?:BKN|OVC|VV)(\d{3})(?:CB|TCU)?', token)
                if not match:
                    raise ValueError()
                raw_ceilings.append(float(match[1]) * 100)
        if sorted(raw_ceilings) != sorted(ceilings):
            raise ValueError()
        if not clouds and not any(t in ('CLR', 'SKC', 'NSC', 'NCD', 'CAVOK') for t in tokens):
            raise ValueError()
        w.ceiling_ft = min(ceilings) if ceilings else None
    except (ValueError, TypeError, OverflowError):
        w.issues.append('Cloud/ceiling information is missing, malformed, or inconsistent.')
    try:
        wind_tokens = [t for t in tokens if t.endswith('KT')]
        if len(wind_tokens) != 1:
            raise ValueError()
        match = re.fullmatch(r'(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?KT', wind_tokens[0])
        if not match:
            raise ValueError()
        w.wind_speed_kt = number(data.get('wspd'))
        w.wind_gust_kt = number(data['wgst']) if data.get('wgst') is not None else None
        if w.wind_speed_kt != float(match[2]) or w.wind_gust_kt != (float(match[3]) if match[3] else None):
            raise ValueError()
        if w.wind_gust_kt is not None and w.wind_gust_kt < w.wind_speed_kt:
            raise ValueError()
        direction = data.get('wdir')
        if match[1] == 'VRB':
            if direction != 'VRB':
                raise ValueError()
            w.is_variable_wind = True
        else:
            w.wind_direction = number(direction)
            if w.wind_direction > 360 or w.wind_direction != float(match[1]):
                raise ValueError()
            if w.wind_direction == 0 and (w.wind_speed_kt or w.wind_gust_kt):
                raise ValueError()
        # Full-speed conservative crosswind for any directional variability group.
        for token in tokens:
            if re.match(r'[\d/]{3}V', token):
                if not re.fullmatch(r'\d{3}V\d{3}', token) or any(int(v) > 360 for v in token.split('V')):
                    raise ValueError()
                w.is_variable_wind = True
    except (ValueError, TypeError, OverflowError):
        w.issues.append('Wind information is missing, malformed, or inconsistent.')
    return w

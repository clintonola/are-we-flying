"""One bounded request per weather command; no background polling or retries."""
import logging
import requests

log = logging.getLogger(__name__)

class WeatherError(Exception):
    pass

def fetch_metar(airport: str) -> dict:
    try:
        response = requests.get('https://aviationweather.gov/api/data/metar',
            params={'ids': airport, 'format': 'json'},
            headers={'User-Agent': 'AreWeFlying/1.0 (local personal-minimum weather checker)'},
            timeout=(5, 10))
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        log.warning('AWC request failed (%s)', type(exc).__name__)
        raise WeatherError('Aviation Weather API unavailable or returned invalid JSON.') from exc
    if not isinstance(data, list) or not data:
        raise WeatherError('Aviation Weather API returned no observations.')
    # Default endpoint should return one current observation. Ambiguity is unsafe.
    if len(data) != 1 or not isinstance(data[0], dict):
        raise WeatherError('Aviation Weather API returned an unexpected response.')
    log.info('AWC request successful for %s', airport)
    return data[0]

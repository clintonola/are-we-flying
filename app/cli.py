import argparse
from dataclasses import replace
import logging
from dotenv import load_dotenv
from .config import Settings
from .aviation_weather import fetch_metar, WeatherError
from .weather_parser import parse_weather
from .evaluator import evaluate
from .sms import format_evaluation, unknown
from .demo import scenario

def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    p = argparse.ArgumentParser(description='Local weather checks; never sends SMS.')
    commands = p.add_subparsers(dest='command', required=True)
    commands.add_parser('weather')
    demo = commands.add_parser('demo')
    demo.add_argument('scenario', choices=['good', 'crosswind', 'ceiling', 'visibility', 'wind', 'ifr'])
    args = p.parse_args()
    try:
        s = Settings.from_env()
        if args.command == 'demo':
            print('DEMO — SYNTHETIC WEATHER — NOT FOR FLIGHT\nSynthetic magnetic variation: 0°\n')
            s = replace(s, magnetic_variation_deg=0)
            data = scenario(args.scenario)
        else:
            data = fetch_metar(s.airport)
        w = parse_weather(data, s.airport)
        e = evaluate(w, s)
        print(f'Airport: {s.airport}\n')
        print(format_evaluation(w, e))
        print(f'\nRESULT: {e.status}')
        for c in e.runway_components:
            head = 'unknown' if c.headwind_kt is None else f'{c.headwind_kt:.1f} kt (negative = tailwind)'
            print(f'Runway {c.runway}: headwind {head}; crosswind {c.crosswind_kt:.1f} kt')
    except (WeatherError, ValueError) as exc:
        print(unknown(str(exc)))
        print('\nRESULT: UNKNOWN')

if __name__ == '__main__':
    main()

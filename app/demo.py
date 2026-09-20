"""Synthetic scenarios; never imported by the webhook."""
from datetime import datetime, timezone

def scenario(name: str) -> dict:
    speed, direction, vis, base, category = 5, 270, 10, 8000, 'VFR'
    if name == 'crosswind': speed, direction = 18, 180
    elif name == 'ceiling': base = 3500
    elif name == 'visibility': vis = 4
    elif name == 'wind': speed = 27
    elif name == 'ifr': base, vis, category = 700, 2, 'IFR'
    elif name != 'good': raise ValueError('Unknown demo scenario')
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    return {'icaoId': 'KRYY', 'rawOb': f'KRYY {now:%d%H%M}Z {direction:03d}{speed:02d}KT {vis}SM BKN{base // 100:03d} 20/10 A3000',
            'obsTime': now.timestamp(), 'fltCat': category, 'visib': vis,
            'wdir': direction, 'wspd': speed, 'wgst': None, 'clouds': [{'cover': 'BKN', 'base': base}]}

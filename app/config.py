"""Personal minimums and airport geometry: edit this single configuration module."""
from dataclasses import dataclass, field
import math
import os
import re
from urllib.parse import urlsplit

@dataclass(frozen=True)
class Minimums:
    visibility_sm: float = 5
    ceiling_ft: float = 4000
    max_wind_kt: float = 25
    max_crosswind_kt: float = 10
    flight_category: str = 'VFR'
    max_age_minutes: float = 90

@dataclass(frozen=True)
class Runway:
    name: str
    magnetic_heading: float

@dataclass(frozen=True)
class Settings:
    airport: str = 'KRYY'
    minimums: Minimums = field(default_factory=Minimums)
    runways: tuple[Runway, ...] = (Runway('09', 94), Runway('27', 274))
    # East positive, west negative. None deliberately prevents directional PASS.
    magnetic_variation_deg: float | None = None
    account_sid: str = ''
    auth_token: str = ''
    twilio_phone: str = ''
    allowed_phone: str = ''
    webhook_url: str = ''
    whatsapp_phone: str = ''

    def __post_init__(self) -> None:
        if self.whatsapp_phone and not re.fullmatch(r'whatsapp:\+[1-9]\d{7,14}', self.whatsapp_phone):
            raise ValueError('TWILIO_WHATSAPP_NUMBER must use whatsapp:+countrycode format')
        if not re.fullmatch(r'[A-Z][A-Z0-9]{3}', self.airport):
            raise ValueError('AIRPORT_ID must be a four-character ICAO identifier')
        values = (self.minimums.visibility_sm, self.minimums.ceiling_ft,
                  self.minimums.max_wind_kt, self.minimums.max_crosswind_kt,
                  self.minimums.max_age_minutes)
        if any(not math.isfinite(v) or v < 0 for v in values):
            raise ValueError('Minimums must be finite and nonnegative')
        if self.minimums.flight_category != 'VFR':
            raise ValueError('This version requires VFR')
        if not self.runways or any(not math.isfinite(r.magnetic_heading) or not 0 <= r.magnetic_heading < 360 for r in self.runways):
            raise ValueError('Invalid runway configuration')
        if self.magnetic_variation_deg is not None and (not math.isfinite(self.magnetic_variation_deg) or abs(self.magnetic_variation_deg) > 180):
            raise ValueError('Invalid magnetic variation')

    @classmethod
    def from_env(cls, require_sms: bool = False) -> 'Settings':
        airport = os.getenv('AIRPORT_ID', 'KRYY').strip().upper()
        if airport != 'KRYY':
            raise ValueError('Configure runway geometry in config.py before changing AIRPORT_ID')
        variation = os.getenv('MAGNETIC_VARIATION_DEG', '').strip()
        s = cls(airport=airport, magnetic_variation_deg=float(variation) if variation else None,
                account_sid=os.getenv('TWILIO_ACCOUNT_SID', ''), auth_token=os.getenv('TWILIO_AUTH_TOKEN', ''),
                twilio_phone=os.getenv('TWILIO_PHONE_NUMBER', ''), allowed_phone=os.getenv('ALLOWED_PHONE_NUMBER', ''),
                webhook_url=os.getenv('PUBLIC_WEBHOOK_URL', ''),
                whatsapp_phone=os.getenv('TWILIO_WHATSAPP_NUMBER', '').strip())
        if require_sms:
            if not re.fullmatch(r'AC[0-9a-fA-F]{32}', s.account_sid) or not s.auth_token:
                raise ValueError('Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in .env')
            if any(not re.fullmatch(r'\+[1-9]\d{7,14}', p) for p in (s.twilio_phone, s.allowed_phone)):
                raise ValueError('Set TWILIO_PHONE_NUMBER and ALLOWED_PHONE_NUMBER in E.164 format')
            u = urlsplit(s.webhook_url)
            if u.scheme != 'https' or not u.hostname or u.path != '/sms' or u.query or u.fragment or u.username:
                raise ValueError('PUBLIC_WEBHOOK_URL must be the exact HTTPS ngrok URL ending in /sms')
        return s

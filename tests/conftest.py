from datetime import datetime, timezone
import pytest
from app.demo import scenario
from app.config import Settings

@pytest.fixture
def data():
    return scenario('good')

@pytest.fixture
def settings():
    return Settings(magnetic_variation_deg=0, account_sid='AC' + '0' * 32,
        auth_token='test-token-not-a-secret', twilio_phone='+15555550100',
        allowed_phone='+15555550101', webhook_url='https://example.ngrok-free.app/sms')

@pytest.fixture(autouse=True)
def prevent_live_requests(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError('Live HTTP requests are forbidden in tests')
    monkeypatch.setattr('requests.sessions.Session.request', blocked)

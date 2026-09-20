from unittest.mock import Mock
import xml.etree.ElementTree as ET
import pytest
from twilio.request_validator import RequestValidator
from app import create_app
from app.aviation_weather import WeatherError

@pytest.fixture
def client(settings):
    return create_app(settings).test_client()

def post(client,settings,body,**changes):
    form=dict(From=settings.allowed_phone,To=settings.twilio_phone,AccountSid=settings.account_sid,Body=body)
    form.update(changes)
    sig=RequestValidator(settings.auth_token).compute_signature(settings.webhook_url,form)
    return client.post('/sms',data=form,headers={'X-Twilio-Signature':sig})

@pytest.mark.parametrize('cmd', ['ARE WE FLYING?','FLY','FLY?','WEATHER','CAN I FLY?','  are   we flying!!! '])
def test_weather(client,settings,data,monkeypatch,cmd):
    fetch=Mock(return_value=data); monkeypatch.setattr('app.routes.fetch_metar',fetch)
    r=post(client,settings,cmd)
    assert r.status_code == 200
    assert "WE'RE FLYING" in ET.fromstring(r.data).find('Message').text
    fetch.assert_called_once_with('KRYY')

@pytest.mark.parametrize('cmd,text', [('METAR','Observed:'),('LIMITS','MY PERSONAL MINIMUMS'),('HELP','Show commands.'),('nonsense',"don't recognize")])
def test_commands(client,settings,data,monkeypatch,cmd,text):
    fetch=Mock(return_value=data); monkeypatch.setattr('app.routes.fetch_metar',fetch)
    r=post(client,settings,cmd)
    assert text in ET.fromstring(r.data).find('Message').text
    assert fetch.call_count == (1 if cmd=='METAR' else 0)

@pytest.mark.parametrize('changes',[{'From':'+15555550999'},{'To':'+15555550999'},{'AccountSid':'AC'+'1'*32}])
def test_unauthorized(client,settings,monkeypatch,changes):
    fetch=Mock(); monkeypatch.setattr('app.routes.fetch_metar',fetch)
    r=post(client,settings,'FLY',**changes)
    assert r.status_code == 200
    assert ET.fromstring(r.data).find('Message') is None
    fetch.assert_not_called()

def test_invalid_signature(client,monkeypatch):
    fetch=Mock(); monkeypatch.setattr('app.routes.fetch_metar',fetch)
    assert client.post('/sms',data={'Body':'FLY'},headers={'X-Twilio-Signature':'fake','X-Forwarded-Host':'evil'}).status_code==403
    fetch.assert_not_called()

def test_api_error(client,settings,monkeypatch):
    monkeypatch.setattr('app.routes.fetch_metar',Mock(side_effect=WeatherError('API unavailable.')))
    assert 'WEATHER CHECK NEEDED' in post(client,settings,'FLY').text

def test_unexpected_error(client,settings,monkeypatch):
    monkeypatch.setattr('app.routes.fetch_metar',Mock(side_effect=RuntimeError('internal detail')))
    r=post(client,settings,'FLY')
    assert 'WEATHER CHECK NEEDED' in r.text
    assert 'internal detail' not in r.text

def test_health(client):
    assert client.get('/health').json == {'status':'ok'}
    assert client.get('/').status_code == 200

def test_signed_for_wrong_url(client,settings):
    form=dict(From=settings.allowed_phone,To=settings.twilio_phone,AccountSid=settings.account_sid,Body='FLY')
    sig=RequestValidator(settings.auth_token).compute_signature('http://localhost:5000/sms',form)
    assert client.post('/sms',data=form,headers={'X-Twilio-Signature':sig}).status_code == 403

def test_tampered_body(client,settings):
    form=dict(From=settings.allowed_phone,To=settings.twilio_phone,AccountSid=settings.account_sid,Body='HELP')
    sig=RequestValidator(settings.auth_token).compute_signature(settings.webhook_url,form)
    form['Body']='FLY'
    assert client.post('/sms',data=form,headers={'X-Twilio-Signature':sig}).status_code == 403

def test_query_rejected(client):
    assert client.post('/sms?anything=1',data={'Body':'FLY'}).status_code == 403

def test_demo_not_exposed(client,settings,monkeypatch):
    fetch=Mock(); monkeypatch.setattr('app.routes.fetch_metar',fetch)
    assert "don't recognize" in post(client,settings,'demo good').text
    assert client.get('/demo/good').status_code == 404
    fetch.assert_not_called()

def test_missing_identity(client,settings):
    form={'Body':'HELP'}
    sig=RequestValidator(settings.auth_token).compute_signature(settings.webhook_url,form)
    assert client.post('/sms',data=form,headers={'X-Twilio-Signature':sig}).status_code == 403

def test_xml_escaping(client,settings,data,monkeypatch):
    data['rawOb'] += ' RMK <test>&'
    monkeypatch.setattr('app.routes.fetch_metar',Mock(return_value=data))
    r=post(client,settings,'METAR')
    assert '<test>&' in ET.fromstring(r.data).find('Message').text

def test_stale_sms(client,settings,data,monkeypatch):
    data['obsTime'] -= 91*60
    monkeypatch.setattr('app.routes.fetch_metar',Mock(return_value=data))
    assert 'WEATHER CHECK NEEDED' in post(client,settings,'FLY').text

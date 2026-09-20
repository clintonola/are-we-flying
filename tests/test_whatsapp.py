from dataclasses import replace
from unittest.mock import Mock
import xml.etree.ElementTree as ET
import pytest
from twilio.request_validator import RequestValidator
from app import create_app

@pytest.fixture
def whatsapp(settings):
    return replace(settings, whatsapp_phone='whatsapp:+14155238886')

def request(s, body='LIMITS', **changes):
    form={'From':'whatsapp:'+s.allowed_phone, 'To':s.whatsapp_phone,
          'AccountSid':s.account_sid,'Body':body}
    form.update(changes)
    signature=RequestValidator(s.auth_token).compute_signature(s.webhook_url,form)
    return create_app(s).test_client().post('/sms',data=form,
        headers={'X-Twilio-Signature':signature})

@pytest.mark.parametrize('body,expected', [('LIMITS','MY PERSONAL MINIMUMS'),('HELP','Show commands.'),('ARE WE FLYING?',"WE'RE FLYING"),('METAR','KRYY METAR')])
def test_whatsapp_commands(whatsapp,data,monkeypatch,body,expected):
    fetch=Mock(return_value=data)
    monkeypatch.setattr('app.routes.fetch_metar',fetch)
    response=request(whatsapp,body)
    assert response.status_code == 200
    assert expected in ET.fromstring(response.data).find('Message').text
    assert fetch.call_count == (1 if body in ('ARE WE FLYING?','METAR') else 0)

@pytest.mark.parametrize('changes',[
    {'From':'whatsapp:+15555550999'}, {'To':'whatsapp:+15555550999'},
    {'From':'+15555550101'}, {'To':'+15555550100'},
    {'From':'telegram:+15555550101'}, {'AccountSid':'AC'+'1'*32}])
def test_wrong_identity_rejected(whatsapp,monkeypatch,changes):
    fetch=Mock();monkeypatch.setattr('app.routes.fetch_metar',fetch)
    response=request(whatsapp,'FLY',**changes)
    assert ET.fromstring(response.data).find('Message') is None
    fetch.assert_not_called()

def test_disabled_by_empty_setting(settings,monkeypatch):
    fetch=Mock();monkeypatch.setattr('app.routes.fetch_metar',fetch)
    response=request(settings,'FLY',To='whatsapp:+14155238886')
    assert ET.fromstring(response.data).find('Message') is None
    fetch.assert_not_called()

def test_whatsapp_requires_signature(whatsapp):
    response=create_app(whatsapp).test_client().post('/sms',data={
        'From':'whatsapp:'+whatsapp.allowed_phone,'To':whatsapp.whatsapp_phone,
        'Body':'LIMITS','AccountSid':whatsapp.account_sid})
    assert response.status_code == 403

@pytest.mark.parametrize('value',['+14155238886','whatsapp:14155238886','whatsapp:+1 415 523 8886'])
def test_invalid_sender_config(settings,value):
    with pytest.raises(ValueError,match='TWILIO_WHATSAPP_NUMBER'):
        replace(settings,whatsapp_phone=value)

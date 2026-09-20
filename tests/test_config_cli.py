from dataclasses import replace
import pytest
from app.config import Settings, Minimums
from app.cli import main

@pytest.mark.parametrize('field,value',[('magnetic_variation_deg',float('nan')),('runways',()),('airport','bad')])
def test_invalid_config(settings,field,value):
    with pytest.raises(ValueError): replace(settings,**{field:value})

def test_bad_minimums():
    with pytest.raises(ValueError): Settings(minimums=Minimums(max_crosswind_kt=-1))

def test_other_airport_guard(monkeypatch):
    monkeypatch.setenv('AIRPORT_ID','KATL')
    with pytest.raises(ValueError,match='geometry'): Settings.from_env()

def test_missing_secrets(monkeypatch):
    monkeypatch.setenv('TWILIO_ACCOUNT_SID','')
    with pytest.raises(ValueError,match='ACCOUNT_SID'): Settings.from_env(require_sms=True)

@pytest.mark.parametrize('name,status',[('good','PASS'),('crosswind','FAIL'),('ceiling','FAIL'),('visibility','FAIL'),('wind','FAIL'),('ifr','FAIL')])
def test_cli_demos(monkeypatch,capsys,name,status):
    monkeypatch.setattr('sys.argv',['cli','demo',name])
    main()
    text=capsys.readouterr().out
    assert 'SYNTHETIC WEATHER' in text
    assert f'RESULT: {status}' in text

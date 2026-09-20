from unittest.mock import Mock
import requests
import pytest
from app.aviation_weather import fetch_metar, WeatherError

@pytest.mark.parametrize('data', [[],{},None,[{},{}],[1]])
def test_bad_shape(monkeypatch,data):
    monkeypatch.setattr('requests.get',Mock(return_value=Mock(json=Mock(return_value=data))))
    with pytest.raises(WeatherError): fetch_metar('KRYY')

@pytest.mark.parametrize('error',[requests.Timeout(),requests.ConnectionError(),requests.HTTPError()])
def test_network(monkeypatch,error):
    monkeypatch.setattr('requests.get',Mock(side_effect=error))
    with pytest.raises(WeatherError): fetch_metar('KRYY')

def test_invalid_json(monkeypatch):
    monkeypatch.setattr('requests.get',Mock(return_value=Mock(json=Mock(side_effect=ValueError()))))
    with pytest.raises(WeatherError): fetch_metar('KRYY')

def test_success(monkeypatch,data):
    get=Mock(return_value=Mock(json=Mock(return_value=[data])))
    monkeypatch.setattr('requests.get',get)
    assert fetch_metar('KRYY') == data
    assert get.call_args.kwargs['timeout'] == (5,10)
    assert get.call_args.kwargs['headers']['User-Agent'].startswith('AreWeFlying/1.0')

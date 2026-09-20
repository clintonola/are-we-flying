from dataclasses import replace
from datetime import datetime, timedelta, timezone
import pytest
from app.evaluator import evaluate
from app.weather_parser import parse_weather
from app.models import Status

def check(data,settings):
    w=parse_weather(data,'KRYY')
    return evaluate(w,settings,now=w.observation_time)

@pytest.mark.parametrize('key,value,criterion,expected', [
    ('visib',4,'visibility_pass',False),('visib',5,'visibility_pass',True),
    ('fltCat','IFR','flight_category_pass',False),('fltCat','MVFR','flight_category_pass',False),('fltCat','LIFR','flight_category_pass',False)])
def test_criteria(data,settings,key,value,criterion,expected):
    data[key]=value
    if key == 'visib': data['rawOb']=data['rawOb'].replace('10SM',f'{value}SM')
    e=check(data,settings)
    assert getattr(e,criterion) is expected
    assert e.status == (Status.PASS if expected else Status.FAIL)

def test_perfect(data,settings):
    assert check(data,settings).status == Status.PASS

@pytest.mark.parametrize('base,expected',[(3500,False),(4000,True)])
def test_ceiling(data,settings,base,expected):
    data['clouds'][0]['base']=base
    data['rawOb']=data['rawOb'].replace('BKN080',f'BKN{base//100:03d}')
    assert check(data,settings).ceiling_pass is expected

@pytest.mark.parametrize('direction,speed,gust,wind_ok,cross_ok,runway',[
    (270,26,None,False,True,'27'),(270,25,None,True,True,'27'),
    (270,18,27,False,True,'27'),(270,18,25,True,True,'27'),
    (184,11,None,True,False,'09'),(184,10,None,True,True,'09'),
    (184,8,14,True,False,'09'),(94,25,None,True,True,'09'),
    (274,25,None,True,True,'27'),(0,0,None,True,True,'09'),
    ('VRB',8,None,True,True,None),('VRB',14,None,True,False,None),
    ('VRB',14,20,True,False,None)])
def test_winds(data,settings,direction,speed,gust,wind_ok,cross_ok,runway):
    d=direction if isinstance(direction,str) else f'{direction:03d}'
    token=f'{d}{speed:02d}'+(f'G{gust:02d}' if gust is not None else '')+'KT'
    data.update(wdir=direction,wspd=speed,wgst=gust)
    data['rawOb']=data['rawOb'].replace('27005KT',token)
    e=check(data,settings)
    assert e.wind_pass is wind_ok
    assert e.crosswind_pass is cross_ok
    assert e.selected_runway == runway
    if direction == 'VRB': assert e.crosswind_kt == max(speed,gust or 0)

@pytest.mark.parametrize('age,status',[(90,Status.PASS),(90.001,Status.UNKNOWN),(104,Status.UNKNOWN),(-.01,Status.UNKNOWN)])
def test_age(data,settings,age,status):
    now=datetime.now(timezone.utc)
    observed=now-timedelta(minutes=age)
    data['obsTime']=observed.timestamp()
    import re
    data['rawOb']=re.sub(r'\d{6}Z', observed.strftime('%d%H%MZ'), data['rawOb'])
    assert evaluate(parse_weather(data,'KRYY'),settings,now).status == status

@pytest.mark.parametrize('key', ['obsTime','visib','wspd','fltCat','clouds'])
def test_missing_overrides_fail(data,settings,key):
    data['fltCat']='IFR'; data[key]=None
    assert evaluate(parse_weather(data,'KRYY'),settings).status == Status.UNKNOWN

def test_variation_unset(data,settings):
    assert check(data,replace(settings,magnetic_variation_deg=None)).status == Status.UNKNOWN

def test_multiple_failures(data,settings):
    data.update(visib=2,fltCat='IFR')
    data['rawOb']=data['rawOb'].replace('10SM','2SM')
    e=check(data,settings)
    assert len(e.failure_reasons) == 2

def test_variability_conservative(data,settings):
    data['rawOb']=data['rawOb'].replace('27005KT','27005KT 240V310')
    e=check(data,settings)
    assert e.crosswind_kt == 5
    assert e.selected_runway is None

def test_lower_bound_insufficient(data,settings):
    data['visib']='10+'
    s=replace(settings,minimums=replace(settings.minimums,visibility_sm=11))
    assert check(data,s).status == Status.UNKNOWN

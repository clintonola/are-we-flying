import pytest
from app.weather_parser import parse_weather, visibility

@pytest.mark.parametrize('value,expected', [(5,5),('5',5),('10+',10),('P6SM',6),('1 1/2',1.5),('3/4',.75),('5.0',5)])
def test_visibility(value, expected):
    assert visibility(value) == expected

@pytest.mark.parametrize('value', [None, True, '', 'NaN', float('inf'), -1, 'M1/4', '1/0', 'garbage'])
def test_bad_visibility(value):
    with pytest.raises((ValueError, ZeroDivisionError)):
        visibility(value)

@pytest.mark.parametrize('layers,raw,expected', [
    ([{'cover':'BKN','base':3500}], 'BKN035',3500),
    ([{'cover':'SCT','base':2500},{'cover':'BKN','base':6000}], 'SCT025 BKN060',6000),
    ([{'cover':'FEW','base':2500},{'cover':'SCT','base':6000}], 'FEW025 SCT060',None),
    ([{'cover':'VV','base':300}], 'VV003',300),
    ([{'cover':'OVX','base':300}], 'VV003',300),
    ([], 'CLR',None),
])
def test_ceiling(data,layers,raw,expected):
    data['clouds']=layers
    data['rawOb']=data['rawOb'].replace('BKN080',raw)
    w=parse_weather(data,'KRYY')
    assert not w.issues
    assert w.ceiling_ft == expected

@pytest.mark.parametrize('key,value', [('obsTime',None),('obsTime','2026-09-19T12:00:00'),('visib',None),('wspd',None),('wdir',999),('clouds',None),('clouds',[]),('clouds',[{'cover':'BKN','base':None}]),('fltCat',None),('icaoId','KATL'),('rawOb',''),('wgst',27)])
def test_missing_malformed(data,key,value):
    data[key]=value
    assert parse_weather(data,'KRYY').issues

def test_obscured_unknown(data):
    data['rawOb']=data['rawOb'].replace('BKN080','VV///')
    data['clouds']=[{'cover':'OVX','base':None}]
    assert parse_weather(data,'KRYY').issues

def test_timezone(data):
    data['obsTime']='2026-09-19T08:00:00-04:00'
    import re
    data['rawOb']=re.sub(r'\d{6}Z','191200Z',data['rawOb'])
    w=parse_weather(data,'KRYY')
    assert not w.issues
    assert w.observation_time.hour == 12

def test_raw_gust_missing_json(data):
    data['rawOb']=data['rawOb'].replace('27005KT','27005G27KT')
    assert parse_weather(data,'KRYY').issues

@pytest.mark.parametrize('old,new', [('10SM','1SM'),('BKN080','BKN///'),('27005KT','27005KT 240V///'),('27005KT','27005KT 240V999'),('BKN080','FEW///'),('BKN080','')])
def test_inconsistent_raw_report(data,old,new):
    data['rawOb']=data['rawOb'].replace(old,new)
    assert parse_weather(data,'KRYY').issues

def test_inconsistent_raw_time(data):
    data['obsTime'] += 3600
    assert parse_weather(data,'KRYY').issues

def test_real_awc_shape():
    import json
    from pathlib import Path
    data=json.loads((Path(__file__).parent/'fixtures'/'awc_kryy.json').read_text())
    w=parse_weather(data,'KRYY')
    assert not w.issues
    assert w.visibility_sm == 10
    assert w.ceiling_ft is None

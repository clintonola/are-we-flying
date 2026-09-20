from dataclasses import replace
import pytest
from app.runway import components, angle_difference, calculate_runways

def test_wrap():
    assert angle_difference(359,1) == -2
    assert angle_difference(1,359) == 2

def test_degrees_and_reciprocals():
    a=components(184,94,10,'09'); b=components(184,274,10,'27')
    assert a.crosswind_kt == pytest.approx(10)
    assert b.crosswind_kt == pytest.approx(10)
    assert a.headwind_kt == pytest.approx(0,abs=1e-9)

def test_variation(settings):
    result=calculate_runways(88,20,False,replace(settings,magnetic_variation_deg=-6))
    assert result[0].headwind_kt == pytest.approx(20)
    assert result[0].crosswind_kt == pytest.approx(0)

import pytest

from benchmarks.district_recovery import assert_safe, radial_fixture


@pytest.mark.parametrize("shape", ["star", "chain"])
def test_generated_radial_fixture_with_two_declared_open_ties(shape):
    district = radial_fixture(shape)
    assert_safe(district)
    assert sum(edge["kind"] == "tie" for edge in district.topology["edges"]) == 2

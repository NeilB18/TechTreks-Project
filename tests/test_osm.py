"""OpenStreetMap lookup, tested with recorded Nominatim answers: no network."""

import json
from pathlib import Path

import pytest

from agent.travel import osm

FIXTURES = Path(__file__).parent / "fixtures" / "osm"


class Resp:
    def __init__(self, name):
        self._data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


@pytest.fixture
def nominatim(monkeypatch):
    """Answers from the recorded fixtures by query, and records each request."""
    answers = {"Versailles Restaurant, Miami": "versailles.json",
               "Vizcaya Museum and Gardens, Miami": "vizcaya.json"}
    calls = []

    def get(url, params, headers, timeout):
        calls.append({"url": url, "params": params, "headers": headers})
        return Resp(answers.get(params["q"], "not_found.json"))
    monkeypatch.setattr(osm.requests, "get", get)
    monkeypatch.setattr(osm, "_cache", {})
    monkeypatch.setattr(osm, "MIN_INTERVAL_S", 0)
    return calls


def test_finds_a_place_with_its_hours(nominatim):
    p = osm.lookup("Versailles Restaurant", "Miami")
    assert (p.name, p.kind) == ("Versailles Restaurant", "amenity/restaurant")
    assert round(p.lat, 2) == 25.76 and round(p.lon, 2) == -80.25
    assert p.opening_hours == "Mo-Th 08:00-24:00; Su 09:00-24:00; Fr-Sa 08:00-01:00"
    assert p.hours[0] == [(480, 1440)] and p.hours[4] == [(480, 1500)]  # Friday closes at 1 am
    assert p.maps_url == "https://www.google.com/maps/search/?api=1&query=Versailles+Restaurant%2C+Miami"
    assert p.osm_url.startswith("https://www.openstreetmap.org/")
    req = nominatim[0]
    assert req["url"] == osm.URL and req["params"]["extratags"] == 1
    assert "TechTreks" in req["headers"]["User-Agent"]  # the usage policy wants the app named


def test_place_without_hours_says_unknown(nominatim):
    p = osm.lookup("Vizcaya Museum and Gardens", "Miami")
    assert p.kind == "leisure/park" and p.opening_hours is None and p.hours is None


def test_not_found_is_none_and_answers_are_cached(nominatim):
    assert osm.lookup("Zzqx Imaginary Taco Palace", "Miami") is None
    assert osm.lookup("zzqx imaginary taco palace ", "miami") is None  # same place, cached
    osm.lookup("Versailles Restaurant", "Miami")
    osm.lookup("Versailles Restaurant", "Miami")
    assert len(nominatim) == 2


def test_requests_are_spaced_a_second_apart(monkeypatch):
    clock = {"now": 100.0}
    sleeps = []
    monkeypatch.setattr(osm.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(osm.time, "sleep", lambda s: sleeps.append(s) or clock.update(now=clock["now"] + s))
    monkeypatch.setattr(osm, "_last_request", 0.0)
    osm._wait_turn()
    clock["now"] += 0.25
    osm._wait_turn()
    assert sleeps == [pytest.approx(0.75)]


@pytest.mark.parametrize("text, expected", [
    ("24/7", {d: [(0, 1440)] for d in range(7)}),
    ("Mo-Fr 09:00-17:00; Sa 10:00-14:00", {**{d: [(540, 1020)] for d in range(5)}, 5: [(600, 840)]}),
    ("11:00-22:00", {d: [(660, 1320)] for d in range(7)}),
    ("Mo-Fr 08:00-12:00,13:00-17:00", {d: [(480, 720), (780, 1020)] for d in range(5)}),
    ("Mo,We,Fr 10:00-18:00", {0: [(600, 1080)], 2: [(600, 1080)], 4: [(600, 1080)]}),
    ("Fr-Mo 18:00-02:00", {d: [(1080, 1560)] for d in (4, 5, 6, 0)}),
    ("Mo-Su 10:00-20:00; Tu off", {d: [(600, 1200)] for d in (0, 2, 3, 4, 5, 6)}),
    ("Mo-Fr 09:00-17:00; PH off", {d: [(540, 1020)] for d in range(5)}),
])
def test_reads_common_opening_hours(text, expected):
    assert osm.parse_opening_hours(text) == expected


@pytest.mark.parametrize("text", ["sunrise-sunset", "Jan-Mar Mo-Fr 09:00-17:00", "Mo-Fr 09:00-17:00 \"call ahead\"",
                                  "by appointment"])
def test_unusual_opening_hours_are_unknown(text):
    assert osm.parse_opening_hours(text) is None

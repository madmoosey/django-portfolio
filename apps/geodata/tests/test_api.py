import pytest
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.geodata.models import County, State


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def mock_geometry():
    # A simple square polygon representing a mock state/county
    poly = Polygon(((0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)))
    return MultiPolygon(poly)


@pytest.fixture
def state(db, mock_geometry):
    return State.objects.create(
        fips_code="99",
        name="Test State",
        abbreviation="TS",
        area_sq_km=100.5,
        population=500000,
        geometry=mock_geometry,
    )


@pytest.fixture
def county(db, state, mock_geometry):
    return County.objects.create(
        fips_code="99001",
        name="Test County",
        state=state,
        area_sq_km=50.25,
        population=250000,
        geometry=mock_geometry,
    )


@pytest.mark.django_db
class TestGeodataAPI:
    def test_state_list(self, api_client, state):
        url = reverse("state-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 1
        
        feature = data["features"][0]
        assert feature["type"] == "Feature"
        assert feature["properties"]["fips_code"] == state.fips_code
        assert feature["properties"]["abbreviation"] == state.abbreviation
        assert feature["geometry"]["type"] == "MultiPolygon"

    def test_county_list(self, api_client, county):
        url = reverse("county-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 1
        
        feature = data["features"][0]
        assert feature["properties"]["fips_code"] == county.fips_code
        assert feature["properties"]["state_name"] == county.state.name
        assert feature["geometry"]["type"] == "MultiPolygon"

    def test_state_filter_bbox(self, api_client, state):
        url = reverse("state-list")
        
        # Bounding box that contains the mock geometry (0,0 to 1,1)
        response = api_client.get(f"{url}?in_bbox=-1,-1,2,2")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["features"]) == 1
        
        # Bounding box that DOES NOT contain the mock geometry
        response = api_client.get(f"{url}?in_bbox=2,2,3,3")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["features"]) == 0

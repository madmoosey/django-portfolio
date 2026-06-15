import logging

from django.conf import settings

from .base import BaseClient

logger = logging.getLogger(__name__)


class GFWClient(BaseClient):
    """Client for the Global Forest Watch Data API."""

    def __init__(self):
        # We use the default GFW data API url
        super().__init__(base_url=settings.GFW_API_BASE_URL)
        self.api_key = settings.GFW_API_KEY

    def _get_headers(self):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def get_county_tree_cover_loss(self, state_fips, county_fips):
        """
        Fetch tree cover loss data for a specific US county.
        Because GFW uses GADM administrative boundaries (iso='USA', adm1=state, adm2=county),
        we would normally issue an SQL query to their dataset API.
        """
        if not self.api_key:
            logger.warning(
                "No GFW_API_KEY found, returning mocked tree cover loss data for testing."
            )
            return self._get_mocked_loss_data(state_fips, county_fips)

        # GFW API Endpoint for UMD Tree Cover Loss
        # Example SQL: SELECT umd_tree_cover_loss__year, SUM(umd_tree_cover_loss__ha)
        # FROM umd_tree_cover_loss WHERE iso = 'USA' AND adm1 = {state_id} AND adm2 = {county_id}
        # GROUP BY umd_tree_cover_loss__year

        # Note: mapping FIPS to GADM IDs can be complex, so in a real production scenario
        # we would either maintain a mapping table or use spatial intersection queries.

        endpoint = "dataset/umd_tree_cover_loss/latest/query"
        sql = f"SELECT umd_tree_cover_loss__year, SUM(umd_tree_cover_loss__ha) as area_ha FROM data WHERE iso = 'USA' AND adm1 = '{state_fips}' AND adm2 = '{county_fips}' GROUP BY umd_tree_cover_loss__year"

        try:
            return self.get(endpoint, params={"sql": sql}, headers=self._get_headers())
        except Exception as e:
            logger.error(f"GFW API Error for county {state_fips}{county_fips}: {e}")
            return None

    def get_county_tree_cover_baseline(self, state_fips, county_fips):
        """Fetch baseline tree cover for the year 2000 or 2010."""
        if not self.api_key:
            return self._get_mocked_baseline_data(state_fips, county_fips)

        endpoint = "dataset/umd_tree_cover_extent_2010/latest/query"
        sql = f"SELECT SUM(umd_tree_cover_extent_2010__ha) as area_ha FROM data WHERE iso = 'USA' AND adm1 = '{state_fips}' AND adm2 = '{county_fips}'"

        try:
            return self.get(endpoint, params={"sql": sql}, headers=self._get_headers())
        except Exception as e:
            logger.error(f"GFW API Error for county {state_fips}{county_fips}: {e}")
            return None

    def _get_mocked_loss_data(self, state_fips, county_fips):
        """Return fake data for local development without an API key."""
        import random

        # Generate random loss data for the last 10 years
        data = []
        for year in range(2013, 2024):
            data.append(
                {
                    "umd_tree_cover_loss__year": year,
                    "area_ha": round(random.uniform(10.0, 500.0), 2),
                }
            )
        return {"data": data}

    def _get_mocked_baseline_data(self, state_fips, county_fips):
        """Return fake baseline data."""
        import random

        return {"data": [{"area_ha": round(random.uniform(5000.0, 50000.0), 2)}]}

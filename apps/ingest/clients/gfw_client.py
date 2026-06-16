import logging

import requests

from django.conf import settings

from .base import BaseClient

logger = logging.getLogger(__name__)

# Standard canopy cover density threshold used by GFW dashboards.
GFW_CANOPY_THRESHOLD = 30


class GFWClient(BaseClient):
    """Client for the Global Forest Watch Data API."""

    def __init__(self):
        super().__init__(base_url=settings.GFW_API_BASE_URL)
        self.api_key = settings.GFW_API_KEY

    def _get_headers(self):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
            headers["Origin"] = "http://localhost:8000"
        return headers

    @staticmethod
    def _fips_to_gadm(state_fips, county_fips):
        """
        Convert US FIPS codes to GFW GADM administrative integers.

        For USA, the GFW GADM IDs map as follows:
          adm1 = int(state_fips)                  e.g. '13' -> 13 (Georgia)
          adm2 = int(county_fips[len(state_fips):]) e.g. '13011' -> 11 (Banks County)

        This mapping was validated against the gadm__tcl__adm2_change dataset.
        """
        adm1 = int(state_fips)
        # County FIPS is 5 digits: first 2 are state, last 3 are county
        adm2 = int(county_fips[len(state_fips) :])
        return adm1, adm2

    def get_county_tree_cover_loss(self, state_fips, county_fips):
        """
        Fetch annual tree cover loss data for a specific US county.

        Uses the pre-aggregated gadm__tcl__adm2_change dataset which returns
        yearly loss without requiring a spatial geometry parameter.
        """
        if not self.api_key:
            logger.warning(
                "No GFW_API_KEY found, returning mocked tree cover loss data for testing."
            )
            return self._get_mocked_loss_data(state_fips, county_fips)

        adm1, adm2 = self._fips_to_gadm(state_fips, county_fips)

        endpoint = "dataset/gadm__tcl__adm2_change/latest/query"
        sql = (
            f"SELECT umd_tree_cover_loss__year, "
            f"SUM(umd_tree_cover_loss__ha) as area_ha, "
            f"SUM(umd_tree_cover_loss_from_fires__ha) as fire_area_ha "
            f"FROM data "
            f"WHERE iso = 'USA' "
            f"AND adm1 = {adm1} "
            f"AND adm2 = {adm2} "
            f"AND umd_tree_cover_density_2000__threshold = {GFW_CANOPY_THRESHOLD} "
            f"GROUP BY umd_tree_cover_loss__year "
            f"ORDER BY umd_tree_cover_loss__year"
        )

        try:
            return self.get(endpoint, params={"sql": sql}, headers=self._get_headers())
        except requests.HTTPError as e:
            logger.error(
                "GFW API Error county=%s status=%s body=%s",
                county_fips,
                e.response.status_code,
                e.response.text,
            )
            raise

    def get_county_tree_cover_baseline(self, state_fips, county_fips):
        """
        Fetch 2010 baseline tree cover extent for a specific US county.

        Uses the pre-aggregated gadm__tcl__adm2_summary dataset which returns
        total tree cover extent without requiring a spatial geometry parameter.
        """
        if not self.api_key:
            return self._get_mocked_baseline_data(state_fips, county_fips)

        adm1, adm2 = self._fips_to_gadm(state_fips, county_fips)

        endpoint = "dataset/gadm__tcl__adm2_summary/latest/query"
        sql = (
            f"SELECT SUM(umd_tree_cover_extent_2010__ha) as area_ha "
            f"FROM data "
            f"WHERE iso = 'USA' "
            f"AND adm1 = {adm1} "
            f"AND adm2 = {adm2} "
            f"AND umd_tree_cover_density_2000__threshold = {GFW_CANOPY_THRESHOLD}"
        )

        try:
            return self.get(endpoint, params={"sql": sql}, headers=self._get_headers())
        except requests.HTTPError as e:
            logger.error(
                "GFW API Error county=%s status=%s body=%s",
                county_fips,
                e.response.status_code,
                e.response.text,
            )
            raise

    def _get_mocked_loss_data(self, state_fips, county_fips):
        """Return fake data for local development without an API key."""
        import random

        data = []
        for year in range(2013, 2024):
            data.append(
                {
                    "umd_tree_cover_loss__year": year,
                    "area_ha": round(random.uniform(10.0, 500.0), 2),
                    "fire_area_ha": round(random.uniform(0.0, 50.0), 2),
                }
            )
        return {"data": data}

    def _get_mocked_baseline_data(self, state_fips, county_fips):
        """Return fake baseline data."""
        import random

        return {"data": [{"area_ha": round(random.uniform(5000.0, 50000.0), 2)}]}

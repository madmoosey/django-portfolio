"""
Management command: seed_geodata

Downloads and ingests US Census Cartographic Boundary Files for States and Counties.
Uses Django's LayerMapping for efficient PostGIS insertion.
"""

import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

from django.contrib.gis.utils import LayerMapping
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.geodata.models import County, State

# URLs for 2022 Cartographic Boundary Files (500k resolution - good balance of detail and size)
STATE_SHP_URL = "https://www2.census.gov/geo/tiger/GENZ2022/shp/cb_2022_us_state_500k.zip"
COUNTY_SHP_URL = "https://www2.census.gov/geo/tiger/GENZ2022/shp/cb_2022_us_county_500k.zip"

# Layer mapping dictionaries
STATE_MAPPING = {
    "fips_code": "STATEFP",
    "name": "NAME",
    "abbreviation": "STUSPS",
    "area_sq_km": "ALAND",  # We will convert square meters to sq km in the model or via override
    "geometry": "MULTIPOLYGON",
}

COUNTY_MAPPING = {
    "fips_code": "GEOID",
    "name": "NAME",
    "area_sq_km": "ALAND",
    "geometry": "MULTIPOLYGON",
}


class Command(BaseCommand):
    """Seed the database with geographic boundaries from the US Census Bureau."""

    help = "Downloads and ingests US Census shapefiles for States and Counties."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing geodata before seeding.",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write(self.style.WARNING("Clearing existing geographic data..."))
            County.objects.all().delete()
            State.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Cleared."))

        # Work in a temporary directory
        temp_dir = Path(tempfile.mkdtemp())
        
        try:
            self.seed_states(temp_dir)
            self.seed_counties(temp_dir)
            self.fix_areas()
            self.stdout.write(self.style.SUCCESS("Successfully seeded geographic data!"))
        finally:
            shutil.rmtree(temp_dir)

    @transaction.atomic
    def seed_states(self, temp_dir: Path):
        """Download and ingest state boundaries."""
        self.stdout.write("Downloading State shapefiles...")
        zip_path = temp_dir / "states.zip"
        urlretrieve(STATE_SHP_URL, zip_path)

        self.stdout.write("Extracting State shapefiles...")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(temp_dir / "states")

        shp_path = temp_dir / "states" / "cb_2022_us_state_500k.shp"

        self.stdout.write("Ingesting State geometries into PostGIS...")
        lm = LayerMapping(
            State,
            str(shp_path),
            STATE_MAPPING,
            transform=True,
            transaction_mode="autocommit",
        )
        lm.save(strict=True, verbose=False)
        self.stdout.write(self.style.SUCCESS(f"Ingested {State.objects.count()} states/territories."))

    @transaction.atomic
    def seed_counties(self, temp_dir: Path):
        """Download and ingest county boundaries."""
        self.stdout.write("Downloading County shapefiles...")
        zip_path = temp_dir / "counties.zip"
        urlretrieve(COUNTY_SHP_URL, zip_path)

        self.stdout.write("Extracting County shapefiles...")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(temp_dir / "counties")

        shp_path = temp_dir / "counties" / "cb_2022_us_county_500k.shp"

        self.stdout.write("Ingesting County geometries into PostGIS...")
        # We need a custom mapping to link County to State via the STATEFP field.
        # LayerMapping doesn't easily handle ForeignKeys automatically if the related field isn't the PK.
        # So we'll parse the shapefile directly using Django's DataSource.
        from django.contrib.gis.gdal import DataSource

        ds = DataSource(str(shp_path))
        layer = ds[0]

        count = 0
        for feat in layer:
            state_fips = feat.get("STATEFP")
            county_fips = feat.get("GEOID")
            name = feat.get("NAME")
            aland = feat.get("ALAND")  # Area land in square meters
            geom = feat.geom.geos
            
            # Ensure geometry is a MultiPolygon
            if geom.geom_type == "Polygon":
                from django.contrib.gis.geos import MultiPolygon
                geom = MultiPolygon(geom)

            try:
                state = State.objects.get(fips_code=state_fips)
                County.objects.update_or_create(
                    fips_code=county_fips,
                    defaults={
                        "name": name,
                        "state": state,
                        "area_sq_km": aland,
                        "geometry": geom,
                    }
                )
                count += 1
                if count % 500 == 0:
                    self.stdout.write(f"  Processed {count} counties...")
            except State.DoesNotExist:
                # E.g., territories we might not have imported depending on the state shapefile
                pass

        self.stdout.write(self.style.SUCCESS(f"Ingested {County.objects.count()} counties."))

    @transaction.atomic
    def fix_areas(self):
        """Convert ALAND from square meters to square kilometers."""
        self.stdout.write("Converting land area from sq meters to sq km...")
        
        # In the Census files, ALAND is in square meters. We'll divide by 1,000,000.
        from django.db.models import F
        
        State.objects.update(area_sq_km=F('area_sq_km') / 1000000)
        County.objects.update(area_sq_km=F('area_sq_km') / 1000000)
        
        self.stdout.write(self.style.SUCCESS("Area conversion complete."))

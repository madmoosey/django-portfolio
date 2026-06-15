import logging

from apps.geodata.models import County

logger = logging.getLogger(__name__)


class FeaturePipeline:
    """Orchestrates the extraction of features from all data domains."""

    def __init__(self, extractors=None):
        self.extractors = extractors or []

    def build_matrix_for_county(self, county, date_ref):
        """Build a single feature dictionary for a county."""
        features = {}
        for extractor in self.extractors:
            try:
                features.update(extractor.extract(county, date_ref))
            except Exception as e:
                logger.error(f"Error extracting features for county {county.fips_code}: {e}")
        return features

    def build_matrix(self, date_ref):
        """Build the feature matrix for all counties."""
        counties = County.objects.all()
        matrix = {}

        for county in counties:
            matrix[county.fips_code] = self.build_matrix_for_county(county, date_ref)

        return matrix

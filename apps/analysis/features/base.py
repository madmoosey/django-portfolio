import abc


class FeatureExtractor(abc.ABC):
    """Abstract base class for extracting machine learning features from raw data."""

    @abc.abstractmethod
    def extract(self, county, date_ref):
        """
        Extract features for a given county at a specific reference date.
        Returns a dictionary of feature names to values.
        """
        pass

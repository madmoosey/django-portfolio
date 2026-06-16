import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const fetchRiskScores = async () => {
  const response = await api.get('/analysis/risk-scores/');
  return response.data;
};

export const fetchActiveAlerts = async () => {
  const response = await api.get('/storms/alerts/');
  return response.data;
};

export const fetchDeforestationLoss = async () => {
  const response = await api.get('/deforestation/loss/');
  return response.data;
};

export const fetchAirQuality = async (limit = 5) => {
  // Returns the top-N worst primary AQI readings (Moderate or worse, sorted by AQI desc)
  const response = await api.get(`/air-quality/observations/?limit=${limit}`);
  return response.data;
};

// ---------------------------------------------------------------------------
// Map overlay endpoints — return bare GeoJSON FeatureCollections
// ---------------------------------------------------------------------------

export const fetchChoroplethCounties = async () => {
  // Lightweight counties with ST_SimplifyPreserveTopology geometry + loss annotations
  const response = await api.get('/geodata/counties/choropleth/');
  return response.data; // bare FeatureCollection { type, count, features }
};

export const fetchAirQualityGeoJSON = async () => {
  // Point features for AQ monitoring stations with AQI properties
  const response = await api.get('/air-quality/observations/geojson/');
  return response.data; // bare FeatureCollection { type, features }
};

export const fetchAlertsGeoJSON = async () => {
  // Paginated GeoJSON FeatureCollection from the DRF router
  const response = await api.get('/storms/alerts/');
  // DRF GeoJsonPagination wraps features in results.features
  const data = response.data;
  const fc = data.results || data; // handle both paginated and bare
  return {
    type: 'FeatureCollection',
    features: fc.features || [],
  };
};

export default api;

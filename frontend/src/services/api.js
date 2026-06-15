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

export default api;

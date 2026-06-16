import React, { useEffect, useState } from 'react';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Loader } from '../components/ui/Loader';
import { AlertTriangle, CloudRain, Trees, Wind } from 'lucide-react';
import { fetchActiveAlerts, fetchDeforestationLoss, fetchAirQuality } from '../services/api';
import './Dashboard.css';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// Map NWS severity to badge colour variant
const severityVariant = (severity) => {
  switch ((severity || '').toLowerCase()) {
    case 'extreme':  return 'danger';
    case 'severe':   return 'danger';
    case 'moderate': return 'warning';
    default:         return 'info';
  }
};

// 1 American football field (incl. end zones) = 360 ft × 160 ft = 0.53512 ha
const HA_PER_FIELD = 0.53512;
const haToFields = (ha) => {
  const fields = Math.round(parseFloat(ha) / HA_PER_FIELD);
  return fields >= 1000
    ? `${(fields / 1000).toFixed(1)}k`
    : fields.toLocaleString();
};

// AQI category labels, badge variants, and colour per EPA breakpoints
const aqiMeta = (aqi) => {
  const n = Number(aqi);
  if (n <= 50)  return { label: 'Good',          variant: 'success' };
  if (n <= 100) return { label: 'Moderate',       variant: 'warning' };
  if (n <= 150) return { label: 'Unhealthy (Sensitive)', variant: 'warning' };
  if (n <= 200) return { label: 'Unhealthy',      variant: 'danger'  };
  if (n <= 300) return { label: 'Very Unhealthy', variant: 'danger'  };
  return               { label: 'Hazardous',      variant: 'danger'  };
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const Dashboard = () => {
  const [alerts, setAlerts]     = useState([]);
  const [lossData, setLossData] = useState([]);
  const [aqData, setAqData]     = useState([]);   // placeholder — wired up by AQ ingestion plan
  const [loading, setLoading]   = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [alertsData, lossResponse, aqResponse] = await Promise.all([
          fetchActiveAlerts(),
          fetchDeforestationLoss(),
          fetchAirQuality(5),
        ]);

        // ActiveAlertSerializer wraps the FeatureCollection inside the DRF
        // pagination envelope: alertsData.results.features
        const featureCollection = alertsData.results || {};
        const rawFeatures = featureCollection.features || [];
        setAlerts(rawFeatures.map(f => ({ id: f.id, ...f.properties })));

        setLossData(lossResponse.results || []);
        setAqData(aqResponse.results || []);
      } catch (error) {
        console.error('Failed to load dashboard data', error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  if (loading) return <Loader />;

  return (
    <div className="dashboard animate-fade-in">
      <header className="dashboard-header">
        <h2>Environmental Overview</h2>
        <p>Real-time insights across deforestation, air quality, and severe weather.</p>
      </header>

      <div className="dashboard-grid dashboard-grid--three">

        {/* ── Column 1: Recent Deforestation ── */}
        <Card className="dashboard-card">
          <div className="card-header">
            <Trees className="card-icon success" size={24} />
            <h3>Recent Deforestation</h3>
          </div>
          <div className="card-content">
            {lossData.length > 0 ? (
              <ul className="alert-list">
                {lossData.slice(0, 5).map(loss => (
                  <li key={loss.id} className="alert-item">
                    <div className="alert-meta">
                      <span className="alert-area">
                        {loss.county_name}, {loss.state_abbreviation} ({loss.year})
                      </span>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.25rem' }}>
                        <Badge variant="danger">
                          {parseFloat(loss.loss_area_ha).toLocaleString()} HA
                        </Badge>
                        <Badge variant="field">
                          🏈 {haToFields(loss.loss_area_ha)} football fields
                        </Badge>
                      </div>
                    </div>
                    <p className="alert-event">Tree cover loss detected.</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted">No recent deforestation data available.</p>
            )}
          </div>
        </Card>

        {/* ── Column 2: Air Quality ── */}
        <Card className="dashboard-card">
          <div className="card-header">
            <Wind className="card-icon aq" size={24} />
            <h3>Air Quality</h3>
          </div>
          <div className="card-content">
            {aqData.length > 0 ? (
              <ul className="alert-list">
                {aqData.slice(0, 5).map(obs => {
                  const { label, variant } = aqiMeta(obs.aqi);
                  return (
                    <li key={obs.id} className="alert-item">
                      <div className="alert-meta">
                        <span className="alert-area">{obs.city}, {obs.state}</span>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.25rem' }}>
                          <Badge variant={variant}>AQI {obs.aqi}</Badge>
                          <Badge variant="info">{obs.pollutant}</Badge>
                        </div>
                      </div>
                      <p className="alert-event">{label}</p>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <div className="aq-coming-soon">
                <Wind size={36} className="aq-placeholder-icon" />
                <p className="text-muted">Air quality ingestion coming soon.</p>
                <p className="aq-sub">
                  Will display real-time EPA AirNow AQI readings for the
                  highest-pollution US counties once the ingestion pipeline
                  is deployed.
                </p>
              </div>
            )}
          </div>
        </Card>

        {/* ── Column 3: Active Severe Weather ── */}
        <Card className="dashboard-card">
          <div className="card-header">
            <CloudRain className="card-icon info" size={24} />
            <h3>Active Severe Weather</h3>
          </div>
          <div className="card-content">
            {alerts.length > 0 ? (
              <ul className="alert-list">
                {alerts.slice(0, 5).map(alert => (
                  <li key={alert.id} className="alert-item">
                    <div className="alert-meta">
                      <span className="alert-area">
                        {alert.affected_zones?.length > 0
                          ? `${alert.affected_zones.length} zone(s) affected`
                          : alert.event_type}
                      </span>
                      <Badge variant={severityVariant(alert.severity)}>
                        {alert.severity}
                      </Badge>
                    </div>
                    <p className="alert-event">{alert.headline || alert.event_type}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted">No active severe weather alerts right now.</p>
            )}
          </div>
        </Card>

      </div>
    </div>
  );
};

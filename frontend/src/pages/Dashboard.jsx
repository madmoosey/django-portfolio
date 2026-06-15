import React, { useEffect, useState } from 'react';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Loader } from '../components/ui/Loader';
import { AlertTriangle, CloudRain, Trees } from 'lucide-react';
import { fetchActiveAlerts, fetchDeforestationLoss } from '../services/api';
import './Dashboard.css';

export const Dashboard = () => {
  const [alerts, setAlerts] = useState([]);
  const [lossData, setLossData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [alertsData, lossResponse] = await Promise.all([
          fetchActiveAlerts(),
          fetchDeforestationLoss()
        ]);
        setAlerts(alertsData.results || []);
        setLossData(lossResponse.results || []);
      } catch (error) {
        console.error("Failed to load dashboard data", error);
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
        <p>Real-time insights across deforestation and severe weather.</p>
      </header>
      
      <div className="dashboard-grid">
        {/* Severe Weather Alerts Card */}
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
                      <span className="alert-area">{alert.area_desc}</span>
                      <Badge variant={alert.severity === 'Severe' ? 'danger' : 'warning'}>
                        {alert.severity}
                      </Badge>
                    </div>
                    <p className="alert-event">{alert.event}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted">No active severe weather alerts right now.</p>
            )}
          </div>
        </Card>

        {/* Deforestation Trends Card */}
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
                      <span className="alert-area">County ID: {loss.county} ({loss.year})</span>
                      <Badge variant="danger">
                        {loss.loss_area_ha} ha
                      </Badge>
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
      </div>
    </div>
  );
};

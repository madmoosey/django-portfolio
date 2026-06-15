import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { Card } from '../components/ui/Card';
import { Loader } from '../components/ui/Loader';
import api from '../services/api';
import './MapViewer.css';

export const MapViewer = () => {
  const [geoData, setGeoData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStates = async () => {
      try {
        const response = await api.get('/geodata/states/');
        setGeoData(response.data);
      } catch (error) {
        console.error("Failed to load map data", error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchStates();
  }, []);

  const styleFeature = (feature) => {
    return {
      fillColor: 'transparent',
      weight: 1,
      opacity: 1,
      color: 'rgba(46, 204, 113, 0.5)',
      fillOpacity: 0.1
    };
  };

  const onEachFeature = (feature, layer) => {
    if (feature.properties && feature.properties.name) {
      layer.bindPopup(feature.properties.name);
    }
    layer.on({
      mouseover: (e) => {
        const layer = e.target;
        layer.setStyle({
          fillColor: 'var(--primary)',
          weight: 2,
          color: 'var(--accent)',
          fillOpacity: 0.4
        });
      },
      mouseout: (e) => {
        const layer = e.target;
        layer.setStyle(styleFeature(feature));
      }
    });
  };

  if (loading) return <Loader />;

  return (
    <div className="map-viewer animate-fade-in">
      <header className="dashboard-header">
        <h2>Interactive Risk Map</h2>
        <p>Geospatial visualization of states and counties.</p>
      </header>
      
      <Card className="map-card">
        <MapContainer center={[39.8283, -98.5795]} zoom={4} className="leaflet-map-container">
          <TileLayer
            attribution='&copy; <a href="https://stadiamaps.com/">Stadia Maps</a>, &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors'
            url="https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png"
          />
          {geoData && (
            <GeoJSON 
              data={geoData} 
              style={styleFeature}
              onEachFeature={onEachFeature}
            />
          )}
        </MapContainer>
      </Card>
    </div>
  );
};

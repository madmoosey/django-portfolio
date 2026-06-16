import React, { useEffect, useState, useMemo, useCallback } from 'react';
import Map, { Source, Layer, Popup } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Card } from '../components/ui/Card';
import { Loader } from '../components/ui/Loader';
import api from '../services/api';
import './MapViewer.css';

export const MapViewer = () => {
  const [geoData, setGeoData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [hoverInfo, setHoverInfo] = useState(null);

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

  const onHover = useCallback(event => {
    const {
      features,
      point: { x, y }
    } = event;
    
    // Check if we're hovering over a feature in the states-layer
    const hoveredFeature = features && features.find(f => f.layer.id === 'states-layer');

    setHoverInfo(hoveredFeature ? {
      feature: hoveredFeature,
      x,
      y
    } : null);
  }, []);

  const onMouseLeave = useCallback(() => {
    setHoverInfo(null);
  }, []);

  const layerStyle = {
    id: 'states-layer',
    type: 'fill',
    paint: {
      'fill-color': 'rgba(46, 204, 113, 0.1)',
      'fill-outline-color': 'rgba(46, 204, 113, 0.3)'
    }
  };

  const highlightLayerStyle = {
    id: 'states-highlight-layer',
    type: 'fill',
    paint: {
      'fill-color': 'rgba(46, 204, 113, 0.4)',
      'fill-outline-color': 'rgba(46, 204, 113, 1)'
    },
    // We use the feature id or a unique property to highlight
    filter: ['==', 'name', hoverInfo?.feature?.properties?.name || '']
  };

  if (loading) return <Loader />;

  return (
    <div className="map-viewer animate-fade-in">
      <header className="dashboard-header">
        <h2>Interactive Risk Map</h2>
        <p>Geospatial visualization of states and counties.</p>
      </header>
      
      <Card className="map-card" style={{ padding: 0 }}>
        <Map
          initialViewState={{
            longitude: -98.5795,
            latitude: 39.8283,
            zoom: 3.5
          }}
          mapStyle="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
          interactiveLayerIds={['states-layer']}
          onMouseMove={onHover}
          onMouseLeave={onMouseLeave}
          style={{ width: '100%', height: '100%', minHeight: '500px' }}
        >
          {geoData && (
            <Source id="states-source" type="geojson" data={geoData}>
              <Layer {...layerStyle} />
              <Layer {...highlightLayerStyle} />
            </Source>
          )}

          {hoverInfo && (
            <div className="map-tooltip" style={{ left: hoverInfo.x, top: hoverInfo.y }}>
              <strong>{hoverInfo.feature.properties.name}</strong>
            </div>
          )}
        </Map>
      </Card>
    </div>
  );
};

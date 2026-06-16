import React, { useCallback, useEffect, useRef, useState } from 'react';
import Map, { Layer, Popup, Source } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Loader } from '../components/ui/Loader';
import {
  fetchAirQualityGeoJSON,
  fetchAlertsGeoJSON,
  fetchChoroplethCounties,
} from '../services/api';
import './MapViewer.css';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Deforestation choropleth colour stops (loss_area_ha → colour) */
const LOSS_COLOR_EXPR = [
  'interpolate', ['linear'],
  ['coalesce', ['get', 'loss_area_ha'], 0],
  0,     'rgba(46, 204, 113, 0.05)',
  500,   'rgba(251, 191, 36, 0.55)',
  5000,  'rgba(239, 68,  68, 0.65)',
  25000, 'rgba(127, 29,  29, 0.85)',
];

/** AQI → circle colour */
const AQI_COLOR_EXPR = [
  'step', ['get', 'aqi'],
  '#fbbf24',   // ≤ 100  Moderate         yellow
  101, '#f97316', // 101–150 Unhealthy/Sens   orange
  151, '#ef4444', // 151–200 Unhealthy         red
  201, '#a855f7', // 201–300 Very Unhealthy    purple
  301, '#7f1d1d', // 301+    Hazardous         maroon
];

/** AQI → circle radius (bigger = worse) */
const AQI_RADIUS_EXPR = [
  'interpolate', ['linear'], ['get', 'aqi'],
  51,  5,
  150, 8,
  300, 12,
];

/** NWS severity → fill colour */
const ALERT_COLOR_EXPR = [
  'match', ['downcase', ['coalesce', ['get', 'severity'], '']],
  'extreme',  'rgba(239, 68,  68, 0.35)',
  'severe',   'rgba(239, 68,  68, 0.25)',
  'moderate', 'rgba(251, 191, 36, 0.25)',
  /* default */ 'rgba(99, 102, 241, 0.18)',
];
const ALERT_OUTLINE_EXPR = [
  'match', ['downcase', ['coalesce', ['get', 'severity'], '']],
  'extreme',  '#ef4444',
  'severe',   '#ef4444',
  'moderate', '#fbbf24',
  /* default */ '#818cf8',
];

const HA_PER_FIELD = 0.53512;
const haToFields = (ha) => {
  if (ha == null) return null;
  const fields = Math.round(parseFloat(ha) / HA_PER_FIELD);
  return fields >= 1000
    ? `${(fields / 1000).toFixed(1)}k`
    : fields.toLocaleString();
};

const fmtDate = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString('en-US', { timeZoneName: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
  catch { return iso; }
};

// ---------------------------------------------------------------------------
// Layer style objects
// ---------------------------------------------------------------------------

const deforestationFill = {
  id: 'deforestation-fill',
  type: 'fill',
  source: 'county-loss',
  paint: { 'fill-color': LOSS_COLOR_EXPR },
};

const deforestationLine = {
  id: 'deforestation-line',
  type: 'line',
  source: 'county-loss',
  paint: { 'line-color': 'rgba(46, 204, 113, 0.15)', 'line-width': 0.4 },
};

const aqCircles = (visible) => ({
  id: 'aq-circles',
  type: 'circle',
  source: 'aq-points',
  layout: { visibility: visible ? 'visible' : 'none' },
  paint: {
    'circle-color': AQI_COLOR_EXPR,
    'circle-radius': AQI_RADIUS_EXPR,
    'circle-stroke-width': 1.5,
    'circle-stroke-color': 'rgba(255,255,255,0.3)',
    'circle-opacity': 0.9,
  },
});

const alertsFill = (visible) => ({
  id: 'alerts-fill',
  type: 'fill',
  source: 'alerts-polygons',
  layout: { visibility: visible ? 'visible' : 'none' },
  paint: { 'fill-color': ALERT_COLOR_EXPR },
});

const alertsLine = (visible) => ({
  id: 'alerts-line',
  type: 'line',
  source: 'alerts-polygons',
  layout: { visibility: visible ? 'visible' : 'none' },
  paint: { 'line-color': ALERT_OUTLINE_EXPR, 'line-width': 1.5 },
});

// ---------------------------------------------------------------------------
// Popup content renderers
// ---------------------------------------------------------------------------

function DeforestationPopup({ p }) {
  const fields = haToFields(p.loss_area_ha);
  return (
    <div className="mp-body">
      <div className="mp-title">{p.name}</div>
      <div className="mp-sub">{p.state_abbreviation} · FIPS {p.fips_code}</div>
      {p.loss_area_ha != null ? (
        <>
          <div className="mp-row">
            <span className="mp-label">Year</span>
            <span className="mp-value">{p.loss_year ?? '—'}</span>
          </div>
          <div className="mp-row">
            <span className="mp-label">Loss</span>
            <span className="mp-value mp-danger">{parseFloat(p.loss_area_ha).toLocaleString()} ha</span>
          </div>
          {fields && (
            <div className="mp-row">
              <span className="mp-label">Equiv.</span>
              <span className="mp-value mp-field">🏈 {fields} football fields</span>
            </div>
          )}
        </>
      ) : (
        <div className="mp-no-data">No loss data recorded</div>
      )}
    </div>
  );
}

function AQPopup({ p }) {
  const aqiClass =
    p.aqi > 300 ? 'mp-hazardous'
    : p.aqi > 200 ? 'mp-very-unhealthy'
    : p.aqi > 150 ? 'mp-unhealthy'
    : p.aqi > 100 ? 'mp-unhealthy-sensitive'
    : 'mp-moderate';

  return (
    <div className="mp-body">
      <div className="mp-title">{p.reporting_area}</div>
      <div className="mp-sub">{p.state_abbreviation}{p.county_name ? ` · ${p.county_name}` : ''}</div>
      <div className="mp-row">
        <span className="mp-label">AQI</span>
        <span className={`mp-value mp-aqi ${aqiClass}`}>{p.aqi}</span>
      </div>
      <div className="mp-row">
        <span className="mp-label">Category</span>
        <span className="mp-value">{p.aqi_category}</span>
      </div>
      <div className="mp-row">
        <span className="mp-label">Pollutant</span>
        <span className="mp-value mp-pollutant">{p.pollutant}</span>
      </div>
      <div className="mp-row">
        <span className="mp-label">Observed</span>
        <span className="mp-value mp-small">{fmtDate(p.observed_at)}</span>
      </div>
    </div>
  );
}

function AlertPopup({ p }) {
  const sevClass =
    p.severity?.toLowerCase() === 'extreme' || p.severity?.toLowerCase() === 'severe'
      ? 'mp-danger'
      : p.severity?.toLowerCase() === 'moderate'
      ? 'mp-warning'
      : 'mp-info';

  return (
    <div className="mp-body">
      <div className="mp-title">{p.event_type}</div>
      <div className="mp-row">
        <span className="mp-label">Severity</span>
        <span className={`mp-value ${sevClass}`}>{p.severity}</span>
      </div>
      <div className="mp-row">
        <span className="mp-label">Urgency</span>
        <span className="mp-value">{p.urgency}</span>
      </div>
      <div className="mp-row mp-headline">
        <span className="mp-value mp-small">{p.headline}</span>
      </div>
      <div className="mp-row">
        <span className="mp-label">Effective</span>
        <span className="mp-value mp-small">{fmtDate(p.effective)}</span>
      </div>
      <div className="mp-row">
        <span className="mp-label">Expires</span>
        <span className="mp-value mp-small">{fmtDate(p.expires)}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

const INTERACTIVE_LAYERS = ['deforestation-fill', 'aq-circles', 'alerts-fill'];

export const MapViewer = () => {
  const [choroplethGeo, setChoroplethGeo] = useState(null);
  const [aqGeo, setAqGeo]               = useState(null);
  const [alertsGeo, setAlertsGeo]        = useState(null);
  const [loading, setLoading]            = useState(true);
  const [loadError, setLoadError]        = useState(null);

  const [showAQ, setShowAQ]           = useState(true);
  const [showAlerts, setShowAlerts]   = useState(true);

  const [cursor, setCursor]      = useState('');
  const [popupInfo, setPopupInfo] = useState(null); // { lngLat, type, props }

  useEffect(() => {
    const load = async () => {
      try {
        const [choropleth, aq, alerts] = await Promise.all([
          fetchChoroplethCounties(),
          fetchAirQualityGeoJSON(),
          fetchAlertsGeoJSON(),
        ]);
        setChoroplethGeo(choropleth);
        setAqGeo(aq);
        setAlertsGeo(alerts);
      } catch (err) {
        console.error('Map data load failed', err);
        setLoadError('Failed to load map data. Is the API running?');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const onMouseEnter = useCallback(() => setCursor('pointer'), []);
  const onMouseLeave = useCallback(() => setCursor(''), []);

  const onClick = useCallback((event) => {
    const feature = event.features?.[0];
    if (!feature) { setPopupInfo(null); return; }

    const lngLat = event.lngLat;
    const { id, layer, properties: p } = feature;

    if (layer.id === 'deforestation-fill') {
      setPopupInfo({ lngLat, type: 'deforestation', props: p });
    } else if (layer.id === 'aq-circles') {
      setPopupInfo({ lngLat, type: 'aq', props: p });
    } else if (layer.id === 'alerts-fill') {
      setPopupInfo({ lngLat, type: 'alert', props: p });
    }
  }, []);

  if (loading) return <Loader />;

  return (
    <div className="map-viewer animate-fade-in">
      <header className="dashboard-header">
        <h2>Interactive Risk Map</h2>
        <p>Deforestation, air quality, and severe weather overlaid across the US.</p>
      </header>

      <div className="map-card">
        <Map
          initialViewState={{ longitude: -98.5795, latitude: 39.8283, zoom: 3.8 }}
          mapStyle="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
          interactiveLayerIds={INTERACTIVE_LAYERS}
          cursor={cursor}
          onMouseEnter={onMouseEnter}
          onMouseLeave={onMouseLeave}
          onClick={onClick}
          style={{ width: '100%', height: '100%' }}
        >
          {/* ── Deforestation choropleth (always on) ── */}
          {choroplethGeo && (
            <Source id="county-loss" type="geojson" data={choroplethGeo}>
              <Layer {...deforestationFill} />
              <Layer {...deforestationLine} />
            </Source>
          )}

          {/* ── Air Quality circles (toggleable) ── */}
          {aqGeo && (
            <Source id="aq-points" type="geojson" data={aqGeo}>
              <Layer {...aqCircles(showAQ)} />
            </Source>
          )}

          {/* ── Severe Weather alert polygons (toggleable) ── */}
          {alertsGeo && (
            <Source id="alerts-polygons" type="geojson" data={alertsGeo}>
              <Layer {...alertsFill(showAlerts)} />
              <Layer {...alertsLine(showAlerts)} />
            </Source>
          )}

          {/* ── Rich popup ── */}
          {popupInfo && (
            <Popup
              longitude={popupInfo.lngLat.lng}
              latitude={popupInfo.lngLat.lat}
              closeButton={true}
              closeOnClick={false}
              onClose={() => setPopupInfo(null)}
              anchor="bottom"
              className="map-popup"
            >
              {popupInfo.type === 'deforestation' && (
                <DeforestationPopup p={popupInfo.props} />
              )}
              {popupInfo.type === 'aq' && (
                <AQPopup p={popupInfo.props} />
              )}
              {popupInfo.type === 'alert' && (
                <AlertPopup p={popupInfo.props} />
              )}
            </Popup>
          )}

          {/* ── Layer toggle controls ── */}
          <div className="map-layer-controls">
            <p className="layer-controls-title">Layers</p>

            <div className="layer-item layer-item--locked">
              <span className="layer-swatch layer-swatch--deforestation" />
              <span className="layer-label">Deforestation</span>
              <span className="layer-lock" title="Always visible">🌿</span>
            </div>

            <label className={`layer-item ${showAQ ? 'layer-item--active' : ''}`}>
              <input
                type="checkbox"
                checked={showAQ}
                onChange={(e) => setShowAQ(e.target.checked)}
              />
              <span className="layer-swatch layer-swatch--aq" />
              <span className="layer-label">Air Quality</span>
            </label>

            <label className={`layer-item ${showAlerts ? 'layer-item--active' : ''}`}>
              <input
                type="checkbox"
                checked={showAlerts}
                onChange={(e) => setShowAlerts(e.target.checked)}
              />
              <span className="layer-swatch layer-swatch--alerts" />
              <span className="layer-label">Severe Weather</span>
            </label>
          </div>

          {/* ── Legend ── */}
          <div className="map-legend">
            <p className="legend-title">Deforestation Intensity</p>
            <div className="legend-scale">
              <div className="legend-row"><span className="legend-chip" style={{ background: 'rgba(46,204,113,0.3)' }} />Low (&lt; 500 ha)</div>
              <div className="legend-row"><span className="legend-chip" style={{ background: 'rgba(251,191,36,0.7)' }} />Moderate (500–5k)</div>
              <div className="legend-row"><span className="legend-chip" style={{ background: 'rgba(239,68,68,0.75)' }} />Severe (5k–25k)</div>
              <div className="legend-row"><span className="legend-chip" style={{ background: 'rgba(127,29,29,0.9)' }} />Extreme (&gt; 25k)</div>
            </div>

            {showAQ && (
              <>
                <p className="legend-title legend-title--sep">Air Quality (AQI)</p>
                <div className="legend-scale">
                  <div className="legend-row"><span className="legend-dot" style={{ background: '#fbbf24' }} />Moderate (51–100)</div>
                  <div className="legend-row"><span className="legend-dot" style={{ background: '#f97316' }} />Unhealthy (101–200)</div>
                  <div className="legend-row"><span className="legend-dot" style={{ background: '#a855f7' }} />Very Unhealthy (200+)</div>
                </div>
              </>
            )}

            {showAlerts && (
              <>
                <p className="legend-title legend-title--sep">Severe Weather</p>
                <div className="legend-scale">
                  <div className="legend-row"><span className="legend-chip" style={{ background: 'rgba(239,68,68,0.4)', border: '1px solid #ef4444' }} />Extreme / Severe</div>
                  <div className="legend-row"><span className="legend-chip" style={{ background: 'rgba(251,191,36,0.35)', border: '1px solid #fbbf24' }} />Moderate</div>
                </div>
              </>
            )}
          </div>

          {/* ── Stats bar ── */}
          <div className="map-stats">
            <span className="stat-item">
              <span className="stat-dot stat-dot--green" />
              {choroplethGeo?.count ?? '—'} counties
            </span>
            {showAQ && (
              <span className="stat-item">
                <span className="stat-dot stat-dot--yellow" />
                {aqGeo?.features?.length ?? 0} AQ stations
              </span>
            )}
            {showAlerts && (
              <span className="stat-item">
                <span className="stat-dot stat-dot--red" />
                {alertsGeo?.features?.length ?? 0} active alerts
              </span>
            )}
          </div>

          {loadError && (
            <div className="map-error">{loadError}</div>
          )}
        </Map>
      </div>
    </div>
  );
};

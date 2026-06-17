import React, { useCallback, useEffect, useRef, useState } from 'react';
import Map, { Layer, Popup, Source } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Loader } from '../components/ui/Loader';
import {
  fetchAirQualityGeoJSON,
  fetchAlertsGeoJSON,
  fetchChoroplethCounties,
  fetchRiskPredictionsBatch,
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

/** Risk score (0-100) → circle colour for prediction layers (Moderate+ only shown) */
const RISK_COLOR_EXPR = [
  'step', ['get', 'score'],
  '#facc15', // 40-59 moderate  yellow
  60, '#f97316', // 60-79 elevated  orange
  80, '#ef4444', // 80+   high      red
];

/** Risk score → circle radius */
const RISK_RADIUS_EXPR = [
  'interpolate', ['linear'], ['get', 'score'],
  0,   4,
  50,  7,
  100, 11,
];

// ---------------------------------------------------------------------------
// Layer style objects
// ---------------------------------------------------------------------------

const deforestationFill = (visible) => ({
  id: 'deforestation-fill',
  type: 'fill',
  source: 'county-loss',
  layout: { visibility: visible ? 'visible' : 'none' },
  paint: { 'fill-color': LOSS_COLOR_EXPR },
});

const deforestationLine = (visible) => ({
  id: 'deforestation-line',
  type: 'line',
  source: 'county-loss',
  layout: { visibility: visible ? 'visible' : 'none' },
  paint: { 'line-color': 'rgba(46, 204, 113, 0.15)', 'line-width': 0.4 },
});

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

const riskLayer = (id, source, visible) => ({
  id,
  type: 'circle',
  source,
  layout: { visibility: visible ? 'visible' : 'none' },
  paint: {
    'circle-color': RISK_COLOR_EXPR,
    'circle-radius': RISK_RADIUS_EXPR,
    'circle-stroke-width': 1,
    'circle-stroke-color': 'rgba(255,255,255,0.2)',
    'circle-opacity': 0.8,
  },
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

function RiskPredictionPopup({ p }) {
  const scoreClass =
    p.score >= 80 ? 'mp-danger'
    : p.score >= 60 ? 'mp-unhealthy'
    : p.score >= 40 ? 'mp-warning'
    : 'mp-moderate';

  const layerCfg = PREDICTION_LAYERS?.find?.(l => l.riskType === p.risk_type);
  const label = layerCfg?.label ?? p.risk_type;

  return (
    <div className="mp-body">
      <div className="mp-title">{label}</div>
      <div className="mp-sub">{p.county_name}{p.state ? `, ${p.state}` : ''}</div>
      <div className="mp-row">
        <span className="mp-label">Risk Score</span>
        <span className={`mp-value mp-aqi ${scoreClass}`}>{p.score}/100</span>
      </div>
      <div className="mp-row">
        <span className="mp-label">Confidence</span>
        <span className="mp-value">{p.confidence}%</span>
      </div>
      {p.factors && typeof p.factors === 'object' && (
        <div className="mp-factors">
          {Object.entries(p.factors).map(([k, v]) => (
            <div key={k} className="mp-row">
              <span className="mp-label mp-factor-key">{k.replace(/_/g, ' ')}</span>
              <span className="mp-value mp-small">{typeof v === 'number' ? v.toFixed(2) : v}</span>
            </div>
          ))}
        </div>
      )}
      <div className="mp-row">
        <span className="mp-label">Computed</span>
        <span className="mp-value mp-small">{fmtDate(p.computed_at)}</span>
      </div>
      <div className="mp-speculative-note">⚠ Speculative — POC model</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

// All layer IDs that respond to click/hover events
const INTERACTIVE_LAYERS = [
  'deforestation-fill', 'aq-circles', 'alerts-fill',
  'aq-risk-circles', 'sw-risk-circles',
  'hur-risk-circles', 'wf-risk-circles', 'heat-risk-circles', 'tor-risk-circles',
];

// Prediction layer config — one entry per event type
// label: exact display text shown in toggles and legend
// color: single accent color for the swatch / legend dot
const PREDICTION_LAYERS = [
  { key: 'aqRisk',   riskType: 'air_quality',   layerId: 'aq-risk-circles',   sourceId: 'aq-risk',   label: 'Prospective Increased Possibility of Air Quality Issues', color: '#22d3ee', emoji: '🌫️' },
  { key: 'swRisk',   riskType: 'severe_weather', layerId: 'sw-risk-circles',   sourceId: 'sw-risk',   label: 'Prospective Increased Possibility of Severe Weather',       color: '#818cf8', emoji: '⛈️' },
  { key: 'hurRisk',  riskType: 'hurricane',      layerId: 'hur-risk-circles',  sourceId: 'hur-risk',  label: 'Prospective Increased Possibility of Hurricane',            color: '#38bdf8', emoji: '🌀' },
  { key: 'wfRisk',   riskType: 'wildfire',       layerId: 'wf-risk-circles',   sourceId: 'wf-risk',   label: 'Prospective Increased Possibility of Wildfire',             color: '#fb923c', emoji: '🔥' },
  { key: 'heatRisk', riskType: 'heat_wave',      layerId: 'heat-risk-circles', sourceId: 'heat-risk', label: 'Prospective Increased Possibility of Heat Wave',            color: '#fbbf24', emoji: '🌡️' },
  { key: 'torRisk',  riskType: 'tornado',        layerId: 'tor-risk-circles',  sourceId: 'tor-risk',  label: 'Prospective Increased Possibility of Tornado',             color: '#a78bfa', emoji: '🌪️' },
];

export const MapViewer = () => {
  const [choroplethGeo, setChoroplethGeo] = useState(null);
  const [aqGeo, setAqGeo]               = useState(null);
  const [alertsGeo, setAlertsGeo]        = useState(null);
  // Prediction layer data: keyed by PREDICTION_LAYERS[].key
  const [predGeo, setPredGeo]            = useState({});
  const [loading, setLoading]            = useState(true);
  const [loadError, setLoadError]        = useState(null);

  const [showDeforestation, setShowDeforestation] = useState(true);
  const [showAQ, setShowAQ]                       = useState(true);
  const [showAlerts, setShowAlerts]               = useState(true);
  // One boolean toggle per prediction layer, keyed by PREDICTION_LAYERS[].key
  const [showPred, setShowPred] = useState(
    Object.fromEntries(PREDICTION_LAYERS.map(l => [l.key, true]))
  );

  const [cursor, setCursor]      = useState('');
  const [popupInfo, setPopupInfo] = useState(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [choropleth, aq, alerts, batchResult] = await Promise.all([
          fetchChoroplethCounties(),
          fetchAirQualityGeoJSON(),
          fetchAlertsGeoJSON(),
          fetchRiskPredictionsBatch(40),  // single request — all 6 types, Moderate+ only
        ]);
        setChoroplethGeo(choropleth);
        setAqGeo(aq);
        setAlertsGeo(alerts);
        const geoByKey = {};
        PREDICTION_LAYERS.forEach(l => { geoByKey[l.key] = batchResult.layers?.[l.riskType] ?? null; });
        setPredGeo(geoByKey);
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

  const INTERACTIVE_LAYERS_COMPUTED = [
    'deforestation-fill', 'aq-circles', 'alerts-fill',
    'aq-risk-circles', 'sw-risk-circles',
  ];

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
    } else if (layer.id === 'aq-risk-circles' || layer.id === 'sw-risk-circles') {
      setPopupInfo({ lngLat, type: 'risk', props: p });
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
          {/* ── Deforestation choropleth (toggleable) ── */}
          {choroplethGeo && (
            <Source id="county-loss" type="geojson" data={choroplethGeo}>
              <Layer {...deforestationFill(showDeforestation)} />
              <Layer {...deforestationLine(showDeforestation)} />
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

          {/* ── ML prediction layers (one per event type) ── */}
          {PREDICTION_LAYERS.map(l => {
            const geo = predGeo[l.key];
            if (!geo?.features?.length) return null;
            return (
              <Source key={l.sourceId} id={l.sourceId} type="geojson" data={geo}>
                <Layer {...riskLayer(l.layerId, l.sourceId, showPred[l.key])} />
              </Source>
            );
          })}

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
              {popupInfo.type === 'risk' && (
                <RiskPredictionPopup p={popupInfo.props} />
              )}
            </Popup>
          )}

          {/* ── Layer toggle controls ── */}
          <div className="map-layer-controls">
            <p className="layer-controls-title">Layers</p>

            <label className={`layer-item ${showDeforestation ? 'layer-item--active' : ''}`}>
              <input
                type="checkbox"
                checked={showDeforestation}
                onChange={(e) => setShowDeforestation(e.target.checked)}
              />
              <span className="layer-swatch layer-swatch--deforestation" />
              <span className="layer-label">Deforestation</span>
            </label>

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

            <p className="layer-controls-section">⚡ Prospective Risk</p>
            {PREDICTION_LAYERS.map(l => {
              const geo = predGeo[l.key];
              const ready = geo?.data_ready !== false && (geo?.features?.length ?? 0) > 0;
              return (
                <label
                  key={l.key}
                  className={`layer-item layer-item--prediction ${showPred[l.key] && ready ? 'layer-item--active' : ''} ${!ready ? 'layer-item--disabled' : ''}`}
                  title={!ready ? 'Prediction data not yet available — task runs daily at 06:30 UTC' : l.label}
                >
                  <input
                    type="checkbox"
                    checked={showPred[l.key]}
                    disabled={!ready}
                    onChange={(e) => setShowPred(prev => ({ ...prev, [l.key]: e.target.checked }))}
                  />
                  <span className="layer-swatch" style={{ background: l.color }} />
                  <span className="layer-label">{l.emoji} {l.label}</span>
                </label>
              );
            })}
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

            {PREDICTION_LAYERS.some(l => showPred[l.key] && (predGeo[l.key]?.features?.length ?? 0) > 0) && (
              <>
                <p className="legend-title legend-title--sep">⚡ Prospective Risk Score</p>
                <p className="legend-subtitle">Showing Moderate and above</p>
                <div className="legend-scale">
                  <div className="legend-row">
                    <span className="legend-dot" style={{ background: '#facc15' }} />
                    Moderate (40–59)
                  </div>
                  <div className="legend-row">
                    <span className="legend-dot" style={{ background: '#f97316' }} />
                    Elevated (60–79)
                  </div>
                  <div className="legend-row">
                    <span className="legend-dot" style={{ background: '#ef4444' }} />
                    <strong>High (80+)</strong>
                  </div>
                </div>
                <div className="legend-event-list">
                  {PREDICTION_LAYERS.filter(l => showPred[l.key] && (predGeo[l.key]?.features?.length ?? 0) > 0).map(l => (
                    <div key={l.key} className="legend-row legend-row--event">
                      <span className="legend-dot" style={{ background: l.color }} />
                      <span style={{ fontSize: '0.65rem', opacity: 0.85 }}>{l.emoji} {l.label}</span>
                      <span className="legend-count">{predGeo[l.key]?.features?.length}</span>
                    </div>
                  ))}
                </div>
                <div className="legend-speculative-badge">⚠ Speculative — POC model</div>
              </>
            )}
          </div>

          {/* ── Stats bar ── */}
          <div className="map-stats">
            {showDeforestation && (
              <span className="stat-item">
                <span className="stat-dot stat-dot--green" />
                {choroplethGeo?.count ?? '—'} counties
              </span>
            )}
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
            {PREDICTION_LAYERS.filter(l => showPred[l.key] && (predGeo[l.key]?.features?.length ?? 0) > 0).map(l => (
              <span key={l.key} className="stat-item">
                <span className="stat-dot" style={{ background: l.color }} />
                {predGeo[l.key]?.features?.length ?? 0} {l.emoji}
              </span>
            ))}
          </div>

          {loadError && (
            <div className="map-error">{loadError}</div>
          )}
        </Map>
      </div>
    </div>
  );
};

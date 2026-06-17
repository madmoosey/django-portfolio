import logging

from django.utils import timezone

from celery import shared_task

from apps.analysis.services import AnalysisService

logger = logging.getLogger(__name__)

# All risk types the inference pipeline supports.
RISK_TYPES = ["heat_wave", "hurricane", "tornado"]


# ---------------------------------------------------------------------------
# Task 1 – Feature matrix build
# ---------------------------------------------------------------------------


@shared_task(bind=True, max_retries=3)
def build_feature_matrix(self, date_ref=None):
    """
    Weekly Celery task to extract features for all counties and persist them
    as FeatureSnapshot records.

    Args:
        date_ref (str | None): ISO date string ('YYYY-MM-DD') to build
            features for.  Defaults to today.  Pass an explicit value to
            trigger a historical backfill.

    Returns:
        dict: {'date_ref': str, 'success': bool}

    Scheduled every Sunday at 04:00 UTC (see config/celery.py).
    predict_county_risk_scores runs at 06:00 UTC and depends on this
    task completing first.
    """
    if date_ref is None:
        date_ref_obj = timezone.now().date()
    else:
        from datetime import date as _date

        date_ref_obj = _date.fromisoformat(date_ref)

    logger.info(f"Starting feature matrix build for date_ref={date_ref_obj}.")

    service = AnalysisService()

    try:
        success = service.build_features(date_ref=date_ref_obj)
    except Exception as exc:
        logger.error(
            f"Feature matrix build failed for {date_ref_obj}: {exc}",
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=300)  # retry after 5 min

    if success:
        logger.info(f"Feature matrix build completed successfully for {date_ref_obj}.")
    else:
        logger.warning(f"Feature matrix build returned False for {date_ref_obj}.")

    return {"date_ref": str(date_ref_obj), "success": bool(success)}


# ---------------------------------------------------------------------------
# Task 2 – Batch risk score inference
# ---------------------------------------------------------------------------


@shared_task(bind=True, max_retries=3)
def predict_county_risk_scores(self, date_ref=None, risk_types=None):
    """
    Weekly Celery task to run inference for all counties using the active
    champion model for each risk type, then persist CountyRiskScore records.

    Each risk type is run independently so a missing/broken model for one
    type does not abort the others.

    Args:
        date_ref (str | None): ISO date string ('YYYY-MM-DD') for the
            reference date.  Defaults to today.
        risk_types (list[str] | None): Subset of risk types to infer.
            Defaults to all three: ['heat_wave', 'hurricane', 'tornado'].

    Returns:
        dict: Mapping of risk_type → {'success': bool, 'error': str | None}

    Scheduled every Sunday at 06:00 UTC (see config/celery.py), two hours
    after build_feature_matrix so snapshots are ready.
    """
    if date_ref is None:
        date_ref_obj = timezone.now().date()
    else:
        from datetime import date as _date

        date_ref_obj = _date.fromisoformat(date_ref)

    targets = risk_types if risk_types else RISK_TYPES

    logger.info(
        f"Starting batch risk prediction for risk_types={targets}, " f"date_ref={date_ref_obj}."
    )

    service = AnalysisService()
    results = {}
    any_success = False

    for risk_type in targets:
        logger.info(f"Running inference: risk_type={risk_type}.")
        try:
            success = service.run_inference(risk_type=risk_type, date_ref=date_ref_obj)
            results[risk_type] = {"success": bool(success), "error": None}
            if success:
                any_success = True
                logger.info(f"Inference completed: risk_type={risk_type}.")
            else:
                logger.warning(
                    f"Inference returned False for risk_type={risk_type}. "
                    "Likely no active model or no feature snapshots."
                )
        except Exception as exc:
            logger.error(
                f"Inference raised an exception for risk_type={risk_type}: {exc}",
                exc_info=True,
            )
            results[risk_type] = {"success": False, "error": str(exc)}

    failed = [rt for rt, r in results.items() if not r["success"]]
    if failed:
        logger.warning(f"Inference failed or skipped for risk_types={failed}.")

    # Retry the whole task only if *every* risk type failed, which indicates a
    # systemic issue (e.g. DB unreachable, no feature snapshots at all).
    if not any_success and targets:
        logger.error(
            "All risk type inferences failed — scheduling retry.",
            extra={"results": results},
        )
        raise self.retry(countdown=600)  # retry after 10 min

    logger.info(
        f"Batch risk prediction finished: "
        f"{len(targets) - len(failed)}/{len(targets)} risk types succeeded."
    )
    return results


# ---------------------------------------------------------------------------
# Task 3 – Environmental risk predictions (air quality + severe weather)
# ---------------------------------------------------------------------------


@shared_task(bind=True, max_retries=2)
def predict_environmental_risks(self, date_ref=None):
    """
    Daily Celery task: score all US counties for air quality risk and severe
    weather risk using live AQ observations and NWS alerts.

    Phase detection (automatic):
      • Phase 1 — rule-based scoring: runs immediately with any data.
      • Phase 2 — XGBoost: activates once ≥ 30 days of FeatureSnapshot
        history exists. Labels are derived self-supervised (did the county
        have a bad event 1-7 days after the snapshot?).

    FeatureSnapshots are saved daily so Phase 2 activates automatically
    after 30 daily runs.

    Returns:
        dict: {phase, aq_saved, sw_saved, date_ref}
    """
    from datetime import date as _date
    from datetime import timedelta

    from apps.analysis.features.air_quality_features import AirQualityFeatureExtractor
    from apps.analysis.features.heat_wave_features import HeatWaveFeatureExtractor
    from apps.analysis.features.hurricane_features import HurricaneFeatureExtractor
    from apps.analysis.features.severe_weather_features import SevereWeatherFeatureExtractor
    from apps.analysis.features.tornado_features import TornadoFeatureExtractor
    from apps.analysis.features.wildfire_features import WildfireFeatureExtractor
    from apps.analysis.ml.air_quality_predictor import FEATURE_COLS as AQ_COLS
    from apps.analysis.ml.air_quality_predictor import AirQualityPredictor
    from apps.analysis.ml.heat_wave import FEATURE_COLS as HEAT_COLS
    from apps.analysis.ml.heat_wave import HeatWavePredictor
    from apps.analysis.ml.hurricane import FEATURE_COLS as HUR_COLS
    from apps.analysis.ml.hurricane import HurricanePredictor
    from apps.analysis.ml.severe_weather_predictor import FEATURE_COLS as SW_COLS
    from apps.analysis.ml.severe_weather_predictor import SevereWeatherPredictor
    from apps.analysis.ml.tornado import FEATURE_COLS as TOR_COLS
    from apps.analysis.ml.tornado import TornadoPredictor
    from apps.analysis.ml.wildfire_predictor import FEATURE_COLS as WF_COLS
    from apps.analysis.ml.wildfire_predictor import WildfirePredictor
    from apps.analysis.models import CountyRiskScore, FeatureSnapshot
    from apps.geodata.models import County

    date_ref_obj = _date.fromisoformat(date_ref) if date_ref else timezone.now().date()
    logger.info(f"[predict_environmental_risks] Starting — date_ref={date_ref_obj}")

    counties = list(County.objects.select_related("state").filter(state__isnull=False))

    # ── Feature extraction ────────────────────────────────────────────────
    aq_extractor = AirQualityFeatureExtractor()
    sw_extractor = SevereWeatherFeatureExtractor()
    hur_extractor = HurricaneFeatureExtractor()
    tor_extractor = TornadoFeatureExtractor()
    heat_extractor = HeatWaveFeatureExtractor()
    wf_extractor = WildfireFeatureExtractor()

    county_features: dict = {}
    for county in counties:
        aq_feats = aq_extractor.extract(county, date_ref_obj)
        sw_feats = sw_extractor.extract(county, date_ref_obj)
        hur_feats = hur_extractor.extract(county, date_ref_obj)
        tor_feats = tor_extractor.extract(county, date_ref_obj)
        heat_feats = heat_extractor.extract(county, date_ref_obj)
        wf_feats = wf_extractor.extract(county, date_ref_obj)
        combined = {**aq_feats, **sw_feats, **hur_feats, **tor_feats, **heat_feats, **wf_feats}
        county_features[county.fips_code] = {"_county": county, **combined}

        # Persist daily snapshot so history accumulates for Phase 2 training
        FeatureSnapshot.objects.update_or_create(
            county=county,
            snapshot_date=date_ref_obj,
            defaults={"features": combined},
        )

    logger.info(f"Features extracted for {len(county_features)} counties.")

    # ── Phase detection: >= 30 days of snapshot history? ─────────────────
    oldest = (
        FeatureSnapshot.objects.order_by("snapshot_date")
        .values_list("snapshot_date", flat=True)
        .first()
    )
    has_30_days = oldest is not None and (date_ref_obj - oldest).days >= 30

    aq_pred = AirQualityPredictor()
    sw_pred = SevereWeatherPredictor()
    hur_pred = HurricanePredictor()
    tor_pred = TornadoPredictor()
    heat_pred = HeatWavePredictor()
    wf_pred = WildfirePredictor()

    if has_30_days:
        logger.info("Phase 2: training XGBoost on historical snapshots.")
        _train_predictor(aq_pred, AQ_COLS, "air_quality", date_ref_obj)
        _train_predictor(sw_pred, SW_COLS, "severe_weather", date_ref_obj)
        _train_predictor(hur_pred, HUR_COLS, "hurricane", date_ref_obj)
        _train_predictor(tor_pred, TOR_COLS, "tornado", date_ref_obj)
        _train_predictor(heat_pred, HEAT_COLS, "heat_wave", date_ref_obj)
        _train_predictor(wf_pred, WF_COLS, "wildfire", date_ref_obj)

    trained = [p._trained for p in [aq_pred, sw_pred, hur_pred, tor_pred, heat_pred, wf_pred]]
    phase = "xgboost" if any(trained) else "rule_based"
    logger.info(f"Active scoring phase: {phase}")

    # ── Score and persist CountyRiskScore records ─────────────────────────
    computed_at = timezone.now()
    window_start_aq = date_ref_obj - timedelta(days=30)
    window_start_sw = date_ref_obj - timedelta(days=90)
    window_start_evt = date_ref_obj - timedelta(days=365 * 10)

    # Each (predictor, risk_type, window_start) tuple is scored independently
    event_configs = [
        (aq_pred, "air_quality", window_start_aq),
        (sw_pred, "severe_weather", window_start_sw),
        (hur_pred, "hurricane", window_start_evt),
        (tor_pred, "tornado", window_start_evt),
        (heat_pred, "heat_wave", window_start_evt),
        (wf_pred, "wildfire", window_start_evt),
    ]

    saved_counts = {cfg[1]: 0 for cfg in event_configs}

    for fips, feats in county_features.items():
        county = feats["_county"]
        for pred, risk_type, win_start in event_configs:
            try:
                score, conf, factors = pred.score_county(feats)
                CountyRiskScore.objects.update_or_create(
                    county=county,
                    risk_type=risk_type,
                    computed_at=computed_at,
                    defaults={
                        "score": score,
                        "confidence": conf,
                        "factors": factors,
                        "data_window_start": win_start,
                        "data_window_end": date_ref_obj,
                    },
                )
                saved_counts[risk_type] += 1
            except Exception as exc:
                logger.error(f"{risk_type} scoring failed for {fips}: {exc}")

    logger.info(f"[predict_environmental_risks] Done — phase={phase}, counts={saved_counts}")
    return {"phase": phase, "saved": saved_counts, "date_ref": str(date_ref_obj)}


def _train_predictor(predictor, feature_cols, risk_type, date_ref):
    """Train predictor on historical FeatureSnapshot data with self-supervised labels."""
    from datetime import timedelta

    import pandas as pd

    from apps.analysis.models import FeatureSnapshot

    snapshots = FeatureSnapshot.objects.select_related("county").filter(
        snapshot_date__lt=date_ref  # exclude today — no future labels yet
    )

    X_rows, y_labels = [], []
    for snap in snapshots:
        if not snap.features:
            continue
        label = _get_label(
            snap.county,
            risk_type,
            snap.snapshot_date + timedelta(days=1),
            snap.snapshot_date + timedelta(days=7),
        )
        if label is None:
            continue
        X_rows.append({col: float(snap.features.get(col, 0)) for col in feature_cols})
        y_labels.append(label)

    if not X_rows or len(set(y_labels)) < 2:
        logger.info(
            f"Skipping XGBoost training for {risk_type}: "
            f"n={len(X_rows)}, distinct_classes={set(y_labels)}"
        )
        return

    predictor.train(pd.DataFrame(X_rows), y_labels)


def _get_label(county, risk_type, label_start, label_end):
    """Return 1/0 if a bad event occurred in the label window, else None."""
    if risk_type == "air_quality":
        from apps.air_quality.models import AirQualityObservation

        return int(
            AirQualityObservation.objects.filter(
                county=county,
                observed_at__date__gte=label_start,
                observed_at__date__lte=label_end,
                aqi__gt=100,
            ).exists()
        )
    elif risk_type == "severe_weather":
        from apps.storms.models import ActiveAlert

        if county.geometry is None:
            return 0
        return int(
            ActiveAlert.objects.filter(
                geometry__intersects=county.geometry,
                effective__date__gte=label_start,
                effective__date__lte=label_end,
                severity__in=["Extreme", "Severe"],
            ).exists()
        )
    return None

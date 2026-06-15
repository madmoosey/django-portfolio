import logging
from celery import shared_task
from django.db import transaction
from apps.geodata.models import County
from apps.deforestation.models import TreeCoverBaseline, TreeCoverLoss
from apps.ingest.clients.gfw_client import GFWClient

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def ingest_tree_cover_loss(self, state_fips=None):
    """
    Celery task to ingest annual tree cover loss data from GFW.
    If state_fips is provided, only ingest for that state.
    """
    client = GFWClient()
    
    counties = County.objects.all()
    if state_fips:
        counties = counties.filter(state__fips_code=state_fips)
        
    logger.info(f"Starting tree cover loss ingestion for {counties.count()} counties.")
    
    success_count = 0
    
    for county in counties:
        try:
            # Step 1: Ingest Baseline (if missing)
            baseline = TreeCoverBaseline.objects.filter(county=county, data_source='GFW').first()
            if not baseline:
                base_data = client.get_county_tree_cover_baseline(county.state.fips_code, county.fips_code)
                if base_data and 'data' in base_data and len(base_data['data']) > 0:
                    area_ha = base_data['data'][0].get('area_ha', 0)
                    
                    # Convert total county area from sq km to hectares (1 sq km = 100 ha)
                    total_area_ha = float(county.area_sq_km) * 100
                    percent = (area_ha / total_area_ha) * 100 if total_area_ha > 0 else 0
                    
                    baseline = TreeCoverBaseline.objects.create(
                        county=county,
                        year=2010,
                        tree_cover_percent=percent,
                        tree_cover_area_ha=area_ha,
                        data_source='GFW',
                        raw_payload=base_data
                    )
            
            # Step 2: Ingest Annual Loss
            loss_data = client.get_county_tree_cover_loss(county.state.fips_code, county.fips_code)
            if loss_data and 'data' in loss_data:
                with transaction.atomic():
                    for record in loss_data['data']:
                        year = record.get('umd_tree_cover_loss__year')
                        area_ha = record.get('area_ha', 0)
                        
                        # Calculate loss percentage relative to baseline
                        if baseline and baseline.tree_cover_area_ha > 0:
                            loss_percent = (area_ha / float(baseline.tree_cover_area_ha)) * 100
                        else:
                            loss_percent = 0
                            
                        TreeCoverLoss.objects.update_or_create(
                            county=county,
                            year=year,
                            data_source='GFW',
                            defaults={
                                'loss_area_ha': area_ha,
                                'loss_percent': loss_percent,
                                'raw_payload': record
                            }
                        )
                success_count += 1
                
        except Exception as e:
            logger.error(f"Failed to ingest data for county {county.name} ({county.fips_code}): {e}")
            
    logger.info(f"Successfully ingested tree cover loss for {success_count}/{counties.count()} counties.")
    return success_count

@shared_task(bind=True, max_retries=3)
def ingest_deforestation_alerts(self, state_fips=None):
    """
    Celery task to ingest near-real-time deforestation alerts (GLAD/RADD).
    """
    logger.info("Starting deforestation alerts ingestion.")
    # Implementation placeholder for alerts
    return 0

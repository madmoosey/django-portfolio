# Tasks package — wildcard imports expose all @shared_task functions to Celery autodiscovery.
from .air_quality_tasks import *  # noqa: F401, F403
from .analysis_tasks import *  # noqa: F401, F403
from .deforestation_tasks import *  # noqa: F401, F403
from .storm_tasks import *  # noqa: F401, F403
from .weather_tasks import *  # noqa: F401, F403

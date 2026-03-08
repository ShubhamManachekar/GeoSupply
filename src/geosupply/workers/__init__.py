"""GeoSupply AI — Workers package.

Exports concrete workers implemented in this repository state.
"""

# Phase 0-1: Core workers
from geosupply.workers.input_sanitiser_worker import InputSanitiserWorker
from geosupply.workers.event_extractor_worker import EventExtractorWorker

# Phase 2: Data Ingestion workers
from geosupply.workers.news_worker import NewsWorker
from geosupply.workers.india_api_worker import IndiaAPIWorker
from geosupply.workers.telegram_worker import TelegramWorker
from geosupply.workers.ais_worker import AISWorker

# Phase 3: NLP and intelligence workers
from geosupply.workers.sentiment_worker import SentimentWorker
from geosupply.workers.ner_worker import NERWorker
from geosupply.workers.claim_worker import ClaimWorker
from geosupply.workers.translation_worker import TranslationWorker
from geosupply.workers.propaganda_worker import PropagandaWorker

__all__ = [
    # Phase 0-1
    "InputSanitiserWorker",
    "EventExtractorWorker",
    # Phase 2
    "NewsWorker",
    "IndiaAPIWorker",
    "TelegramWorker",
    "AISWorker",
    # Phase 3
    "SentimentWorker",
    "NERWorker",
    "ClaimWorker",
    "TranslationWorker",
    "PropagandaWorker",
]

"""GeoSupply AI — Workers package.

Exports all concrete workers implemented in this repository.
"""

# Phase 0-1: Core workers
from geosupply.workers.input_sanitiser_worker import InputSanitiserWorker
from geosupply.workers.event_extractor_worker import EventExtractorWorker

# Phase 2: Data Ingestion workers
from geosupply.workers.news_worker import NewsWorker
from geosupply.workers.india_api_worker import IndiaAPIWorker
from geosupply.workers.telegram_worker import TelegramWorker
from geosupply.workers.ais_worker import AISWorker

# Phase 3: NLP workers
from geosupply.workers.sentiment_worker import SentimentWorker
from geosupply.workers.ner_worker import NERWorker
from geosupply.workers.claim_worker import ClaimWorker
from geosupply.workers.translation_worker import TranslationWorker
from geosupply.workers.propaganda_worker import PropagandaWorker

# Phase 4: Intel workers (Session 18-20)
from geosupply.workers.source_cred_worker import SourceCredWorker
from geosupply.workers.cyber_threat_worker import CyberThreatWorker
from geosupply.workers.supplier_worker import SupplierWorker
from geosupply.workers.sanctions_worker import SanctionsWorker
from geosupply.workers.network_worker import NetworkWorker
from geosupply.workers.cib_worker import CIBWorker
from geosupply.workers.verifier_worker import VerifierWorker
from geosupply.workers.author_worker import AuthorWorker

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
    # Phase 4
    "SourceCredWorker",
    "CyberThreatWorker",
    "SupplierWorker",
    "SanctionsWorker",
    "NetworkWorker",
    "CIBWorker",
    "VerifierWorker",
    "AuthorWorker",
]

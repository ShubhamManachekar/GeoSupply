"""Tests for TranslationWorker."""

import pytest

from geosupply.workers.translation_worker import SUPPORTED_LANGS, TranslationWorker


@pytest.fixture
async def worker():
    w = TranslationWorker()
    await w.setup()
    yield w
    await w.teardown()


class TestTranslationWorkerProcess:
    @pytest.mark.asyncio
    async def test_en_to_hi_translation_lexicon(self, worker):
        res = await worker.process(
            {
                "text": "hello world market",
                "source_lang": "en",
                "target_lang": "hi",
                "trace_id": "t-hi",
            }
        )
        assert "error_type" not in res
        assert res["result"]["translated_text"] == "namaste duniya bazaar"
        assert res["result"]["source_lang"] == "en"
        assert res["result"]["target_lang"] == "hi"

    @pytest.mark.asyncio
    async def test_auto_detects_source_lang(self, worker):
        res = await worker.process(
            {
                "text": "नमस्ते दुनिया",
                "target_lang": "en",
                "trace_id": "t-detect",
            }
        )
        assert "error_type" not in res
        assert res["result"]["source_lang"] == "hi"
        assert res["result"]["translated_text"].startswith("[en]")

    @pytest.mark.asyncio
    async def test_missing_target_lang_returns_error(self, worker):
        res = await worker.process({"text": "hello", "trace_id": "t-miss"})
        assert res["error_type"] == "INPUT_INVALID"
        assert "target_lang" in res["message"]

    @pytest.mark.asyncio
    async def test_unsupported_target_lang_returns_error(self, worker):
        res = await worker.process(
            {
                "text": "hello",
                "source_lang": "en",
                "target_lang": "de",
                "trace_id": "t-bad",
            }
        )
        assert res["error_type"] == "INPUT_INVALID"
        assert "Unsupported target_lang" in res["message"]


class TestTranslationWorkerMeta:
    def test_capabilities(self):
        w = TranslationWorker()
        caps = w.advertise_capabilities()
        assert caps["tier"] == 2
        assert caps["use_static"] is False
        assert "TRANSLATE" in caps["capabilities"]

    def test_supported_langs_has_expected_entries(self):
        assert "en" in SUPPORTED_LANGS
        assert "hi" in SUPPORTED_LANGS
        assert len(SUPPORTED_LANGS) == 12

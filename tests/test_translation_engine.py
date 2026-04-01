#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests unitaires — TranslationEngine (cache + structure)"""

import pytest
from core.translation_engine import TranslationEngine


def test_cache_key_consistency():
    """La même phrase produit toujours la même clé de cache."""
    engine = TranslationEngine(mode="local", source_lang="fr", target_lang="en")
    key1 = engine._cache_key("Bonjour le monde")
    key2 = engine._cache_key("bonjour le monde")  # Normalisé
    assert key1 == key2


def test_empty_text_returns_empty():
    engine = TranslationEngine(mode="local", source_lang="fr", target_lang="en")
    result = engine.translate("   ")
    assert result.translated_text == ""
    assert result.engine_used == "none"


def test_swap_languages():
    engine = TranslationEngine(mode="local", source_lang="fr", target_lang="en")
    engine.swap_languages()
    assert engine.source_lang == "en"
    assert engine.target_lang == "fr"


def test_cache_eviction():
    """Le cache LRU évince les entrées les plus anciennes."""
    engine = TranslationEngine(mode="local", source_lang="fr", target_lang="en", cache_size=2)
    # Remplir manuellement le cache
    from core.translation_engine import TranslationResult
    r = TranslationResult("hello", "fr", "en", "argos", False, 0)
    engine._cache_put(engine._cache_key("bonjour"), r)
    engine._cache_put(engine._cache_key("monde"), r)
    assert len(engine._cache) == 2
    # Ajouter une 3e entrée → la première doit être évincée
    engine._cache_put(engine._cache_key("chat"), r)
    assert len(engine._cache) == 2


def test_set_language_pair():
    engine = TranslationEngine(mode="local", source_lang="fr", target_lang="en")
    engine.set_language_pair("de", "fr")
    assert engine.source_lang == "de"
    assert engine.target_lang == "fr"

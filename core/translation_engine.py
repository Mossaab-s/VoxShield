#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoxShield — Moteur de traduction multi-langues.
Supporte ArgosTranslate (offline) et DeepL API (optionnel).
Cache LRU pour les phrases répétitives. Fallback automatique.
"""

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Literal, Optional

from utils.logger import get_logger

logger = get_logger("TRANS")


@dataclass
class TranslationResult:
    """Résultat d'une traduction."""

    translated_text: str
    source_lang: str
    target_lang: str
    engine_used: str        # 'argos' ou 'deepl'
    from_cache: bool
    processing_ms: int


class TranslationEngine:
    """
    Moteur de traduction bidirectionnel avec cache LRU et fallback automatique.

    Modes :
    - 'local' : ArgosTranslate uniquement (100% offline)
    - 'deepl' : DeepL API uniquement (meilleure qualité, connexion requise)
    - 'auto'  : DeepL si disponible, sinon ArgosTranslate
    """

    def __init__(
        self,
        mode: Literal["local", "deepl", "auto"] = "local",
        source_lang: str = "fr",
        target_lang: str = "en",
        deepl_api_key: Optional[str] = None,
        cache_size: int = 500,
        timeout_ms: int = 3000,
    ) -> None:
        """
        Args:
            mode: Moteur de traduction à utiliser.
            source_lang: Code ISO 639-1 de la langue source.
            target_lang: Code ISO 639-1 de la langue cible.
            deepl_api_key: Clé API DeepL (facultatif).
            cache_size: Nombre maximal d'entrées dans le cache LRU.
            timeout_ms: Timeout DeepL en ms avant fallback local.
        """
        self._mode = mode
        self._source_lang = source_lang
        self._target_lang = target_lang
        self._deepl_api_key = deepl_api_key
        self._cache_size = cache_size
        self._timeout_s = timeout_ms / 1000

        # Cache LRU : clé → TranslationResult
        self._cache: OrderedDict[str, TranslationResult] = OrderedDict()

        # Client DeepL (initialisé à la demande)
        self._deepl_client = None
        self._deepl_available = False

        # Paires ArgosTranslate installées
        self._argos_pairs_installed: set[tuple[str, str]] = set()

        self._init()

    def _init(self) -> None:
        """Initialise les moteurs selon le mode configuré."""
        if self._mode in ("deepl", "auto") and self._deepl_api_key:
            self._init_deepl()

        if self._mode in ("local", "auto"):
            self._ensure_argos_pair(self._source_lang, self._target_lang)

    # ── DeepL ────────────────────────────────────────────────────────────────

    def _init_deepl(self) -> None:
        """Initialise le client DeepL et vérifie la connexion."""
        try:
            import deepl
            self._deepl_client = deepl.Translator(self._deepl_api_key)
            # Test rapide de connectivité
            self._deepl_client.get_usage()
            self._deepl_available = True
            logger.info("DeepL API connecté et disponible")
        except ImportError:
            logger.warning("deepl non installé — DeepL indisponible")
        except Exception as e:
            logger.warning("DeepL non disponible : %s", e)
            self._deepl_available = False

    # ── ArgosTranslate ────────────────────────────────────────────────────────

    def _ensure_argos_pair(self, src: str, tgt: str) -> bool:
        """
        Vérifie que la paire src→tgt est installée dans ArgosTranslate.
        Tente une installation automatique si nécessaire.

        Returns:
            True si la paire est disponible.
        """
        pair = (src, tgt)
        if pair in self._argos_pairs_installed:
            return True

        try:
            import argostranslate.translate as at_translate

            # get_translation() requiert un objet Language (pas un code string)
            installed = at_translate.get_installed_languages()
            src_lang = next((l for l in installed if l.code == src), None)
            tgt_lang = next((l for l in installed if l.code == tgt), None)
            if src_lang and tgt_lang:
                translation = src_lang.get_translation(tgt_lang)
                if translation is not None:
                    self._argos_pairs_installed.add(pair)
                    return True

            # Tenter l'installation automatique
            logger.info("Installation paire Argos %s->%s...", src, tgt)
            return self._install_argos_pair(src, tgt)

        except ImportError:
            logger.warning("argostranslate non installé")
            return False
        except Exception as e:
            logger.error("Erreur vérification paire Argos %s→%s : %s", src, tgt, e)
            return False

    def _install_argos_pair(self, src: str, tgt: str) -> bool:
        """Télécharge et installe un paquet ArgosTranslate."""
        try:
            import argostranslate.package as at_package

            at_package.update_package_index()
            available = at_package.get_available_packages()
            pkg = next(
                (p for p in available if p.from_code == src and p.to_code == tgt),
                None,
            )
            if pkg is None:
                logger.warning("Paire Argos %s→%s non disponible dans l'index", src, tgt)
                return False

            at_package.install_from_path(pkg.download())
            self._argos_pairs_installed.add((src, tgt))
            logger.info("Paire Argos %s→%s installée avec succès", src, tgt)
            return True

        except Exception as e:
            logger.error("Échec installation paire Argos %s→%s : %s", src, tgt, e)
            return False

    def install_language_pair(self, src: str, tgt: str) -> None:
        """Installe explicitement une paire de langues ArgosTranslate."""
        self._install_argos_pair(src, tgt)

    def available_local_pairs(self) -> list[tuple[str, str]]:
        """Retourne les paires de traduction installées localement."""
        try:
            import argostranslate.translate as at_translate
            pairs = []
            for lang in at_translate.get_installed_languages():
                for tgt_lang in at_translate.get_installed_languages():
                    if tgt_lang.code != lang.code:
                        if lang.get_translation(tgt_lang) is not None:
                            pairs.append((lang.code, tgt_lang.code))
            return pairs
        except Exception:
            return []

    # ── Traduction principale ─────────────────────────────────────────────────

    def translate(self, text: str) -> TranslationResult:
        """
        Traduit le texte de source_lang vers target_lang.

        Args:
            text: Texte à traduire.

        Returns:
            TranslationResult avec le texte traduit et les métriques.
        """
        text = text.strip()
        if not text:
            return TranslationResult(
                translated_text="",
                source_lang=self._source_lang,
                target_lang=self._target_lang,
                engine_used="none",
                from_cache=False,
                processing_ms=0,
            )

        # Vérifier le cache LRU
        cache_key = self._cache_key(text)
        cached = self._cache.get(cache_key)
        if cached:
            self._cache.move_to_end(cache_key)
            logger.debug("Cache HIT : '%s...'", text[:40])
            return TranslationResult(
                translated_text=cached.translated_text,
                source_lang=self._source_lang,
                target_lang=self._target_lang,
                engine_used=cached.engine_used,
                from_cache=True,
                processing_ms=0,
            )

        t0 = time.time()
        result = self._do_translate(text)
        result.processing_ms = int((time.time() - t0) * 1000)

        # Stocker dans le cache
        self._cache_put(cache_key, result)

        logger.info(
            "TRANS [%s→%s] '%s' → '%s' (%dms, %s)",
            self._source_lang, self._target_lang,
            text[:50], result.translated_text[:50],
            result.processing_ms, result.engine_used,
        )
        return result

    def _do_translate(self, text: str) -> TranslationResult:
        """Sélectionne le moteur selon le mode configuré."""
        if self._mode == "local":
            return self._translate_argos(text)

        elif self._mode == "deepl":
            if self._deepl_available:
                return self._translate_deepl(text)
            logger.warning("DeepL non disponible — fallback Argos")
            return self._translate_argos(text)

        elif self._mode == "auto":
            if self._deepl_available:
                try:
                    return self._translate_deepl(text)
                except Exception as e:
                    logger.warning("DeepL échoué (%s) — fallback Argos", e)
            return self._translate_argos(text)

        return self._translate_argos(text)

    def _translate_argos(self, text: str) -> TranslationResult:
        """Traduction via ArgosTranslate (offline)."""
        self._ensure_argos_pair(self._source_lang, self._target_lang)
        try:
            import argostranslate.translate as at_translate

            # Utiliser la fonction translate() de haut niveau (la plus robuste)
            translated = at_translate.translate(text, self._source_lang, self._target_lang)
            if translated is None:
                raise RuntimeError(
                    f"Paire {self._source_lang}->{self._target_lang} non disponible dans Argos"
                )
            return TranslationResult(
                translated_text=translated,
                source_lang=self._source_lang,
                target_lang=self._target_lang,
                engine_used="argos",
                from_cache=False,
                processing_ms=0,
            )
        except Exception as e:
            logger.error("Argos traduction échouée : %s", e)
            # Retourner le texte original en cas d'échec total
            return TranslationResult(
                translated_text=text,
                source_lang=self._source_lang,
                target_lang=self._target_lang,
                engine_used="argos_error",
                from_cache=False,
                processing_ms=0,
            )

    def _translate_deepl(self, text: str) -> TranslationResult:
        """Traduction via DeepL API."""
        try:
            from config.language_registry import LANGUAGE_REGISTRY
            target_deepl = LANGUAGE_REGISTRY.get(self._target_lang, {}).get(
                "deepl_code", self._target_lang.upper()
            )
            result = self._deepl_client.translate_text(
                text,
                target_lang=target_deepl,
                timeout=self._timeout_s,
            )
            return TranslationResult(
                translated_text=result.text,
                source_lang=self._source_lang,
                target_lang=self._target_lang,
                engine_used="deepl",
                from_cache=False,
                processing_ms=0,
            )
        except Exception as e:
            logger.warning("DeepL échoué : %s", e)
            raise

    # ── Cache LRU ─────────────────────────────────────────────────────────────

    def _cache_key(self, text: str) -> str:
        normalized = " ".join(text.lower().split())
        raw = f"{normalized}|{self._source_lang}|{self._target_lang}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _cache_put(self, key: str, result: TranslationResult) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._cache_size:
                self._cache.popitem(last=False)  # Supprimer le plus ancien
        self._cache[key] = result

    def clear_cache(self) -> None:
        """Vide le cache de traduction."""
        self._cache.clear()

    # ── Configuration dynamique ───────────────────────────────────────────────

    def set_language_pair(self, source_lang: str, target_lang: str) -> None:
        """Change la paire de langues source/cible."""
        if source_lang != self._source_lang or target_lang != self._target_lang:
            self._source_lang = source_lang
            self._target_lang = target_lang
            self._ensure_argos_pair(source_lang, target_lang)

    def swap_languages(self) -> None:
        """Inverse la paire de langues (src ↔ tgt)."""
        self._source_lang, self._target_lang = self._target_lang, self._source_lang
        self._ensure_argos_pair(self._source_lang, self._target_lang)

    def check_deepl_connection(self) -> bool:
        """Teste la connexion DeepL et met à jour la disponibilité."""
        if not self._deepl_api_key:
            return False
        self._init_deepl()
        return self._deepl_available

    @property
    def source_lang(self) -> str:
        return self._source_lang

    @property
    def target_lang(self) -> str:
        return self._target_lang

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def deepl_available(self) -> bool:
        return self._deepl_available

    def __repr__(self) -> str:
        return (
            f"TranslationEngine(mode={self._mode}, "
            f"{self._source_lang}→{self._target_lang}, "
            f"cache={len(self._cache)}/{self._cache_size})"
        )

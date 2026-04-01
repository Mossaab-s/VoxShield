#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoxShield — Registre complet des langues supportées.
Contient les métadonnées STT, TTS et traduction pour chaque langue.
"""

from typing import Optional

# Registre principal — 20 langues supportées en V1
LANGUAGE_REGISTRY: dict[str, dict] = {
    "fr": {
        "name": "Français",
        "native_name": "Français",
        "flag": "🇫🇷",
        "whisper_code": "fr",
        "deepl_code": "FR",
        "argos_code": "fr",
        "piper_model": "fr_FR-siwis-medium",
        "piper_model_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx"
        ),
        "piper_config_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json"
        ),
        "piper_sample_rate": 22050,
        "rtl": False,
        "needs_openai_tts": False,
        "openai_voice": None,
    },
    "en": {
        "name": "English",
        "native_name": "English",
        "flag": "🇬🇧",
        "whisper_code": "en",
        "deepl_code": "EN-US",
        "argos_code": "en",
        "piper_model": "en_US-lessac-medium",
        "piper_model_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "en/en_US/lessac/medium/en_US-lessac-medium.onnx"
        ),
        "piper_config_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
        ),
        "piper_sample_rate": 22050,
        "rtl": False,
        "needs_openai_tts": False,
        "openai_voice": None,
    },
    "de": {
        "name": "Deutsch",
        "native_name": "Deutsch",
        "flag": "🇩🇪",
        "whisper_code": "de",
        "deepl_code": "DE",
        "argos_code": "de",
        "piper_model": "de_DE-thorsten-medium",
        "piper_model_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx"
        ),
        "piper_config_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx.json"
        ),
        "piper_sample_rate": 22050,
        "rtl": False,
        "needs_openai_tts": False,
        "openai_voice": None,
    },
    "es": {
        "name": "Español",
        "native_name": "Español",
        "flag": "🇪🇸",
        "whisper_code": "es",
        "deepl_code": "ES",
        "argos_code": "es",
        "piper_model": "es_ES-mls_10246-low",
        "piper_model_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "es/es_ES/mls_10246/low/es_ES-mls_10246-low.onnx"
        ),
        "piper_config_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "es/es_ES/mls_10246/low/es_ES-mls_10246-low.onnx.json"
        ),
        "piper_sample_rate": 16000,
        "rtl": False,
        "needs_openai_tts": False,
        "openai_voice": None,
    },
    "it": {
        "name": "Italiano",
        "native_name": "Italiano",
        "flag": "🇮🇹",
        "whisper_code": "it",
        "deepl_code": "IT",
        "argos_code": "it",
        "piper_model": "it_IT-riccardo-x_low",
        "piper_model_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "it/it_IT/riccardo/x_low/it_IT-riccardo-x_low.onnx"
        ),
        "piper_config_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "it/it_IT/riccardo/x_low/it_IT-riccardo-x_low.onnx.json"
        ),
        "piper_sample_rate": 22050,
        "rtl": False,
        "needs_openai_tts": False,
        "openai_voice": None,
    },
    "pt": {
        "name": "Português",
        "native_name": "Português",
        "flag": "🇧🇷",
        "whisper_code": "pt",
        "deepl_code": "PT-BR",
        "argos_code": "pt",
        "piper_model": "pt_BR-faber-medium",
        "piper_model_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx"
        ),
        "piper_config_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json"
        ),
        "piper_sample_rate": 22050,
        "rtl": False,
        "needs_openai_tts": False,
        "openai_voice": None,
    },
    "nl": {
        "name": "Nederlands",
        "native_name": "Nederlands",
        "flag": "🇳🇱",
        "whisper_code": "nl",
        "deepl_code": "NL",
        "argos_code": "nl",
        "piper_model": "nl_NL-mls-medium",
        "piper_model_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "nl/nl_NL/mls/medium/nl_NL-mls-medium.onnx"
        ),
        "piper_config_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "nl/nl_NL/mls/medium/nl_NL-mls-medium.onnx.json"
        ),
        "piper_sample_rate": 22050,
        "rtl": False,
        "needs_openai_tts": False,
        "openai_voice": None,
    },
    "pl": {
        "name": "Polski",
        "native_name": "Polski",
        "flag": "🇵🇱",
        "whisper_code": "pl",
        "deepl_code": "PL",
        "argos_code": "pl",
        "piper_model": "pl_PL-mls_6892-low",
        "piper_model_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "pl/pl_PL/mls_6892/low/pl_PL-mls_6892-low.onnx"
        ),
        "piper_config_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "pl/pl_PL/mls_6892/low/pl_PL-mls_6892-low.onnx.json"
        ),
        "piper_sample_rate": 16000,
        "rtl": False,
        "needs_openai_tts": False,
        "openai_voice": None,
    },
    "ru": {
        "name": "Русский",
        "native_name": "Русский",
        "flag": "🇷🇺",
        "whisper_code": "ru",
        "deepl_code": "RU",
        "argos_code": "ru",
        "piper_model": "ru_RU-irinia-medium",
        "piper_model_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "ru/ru_RU/irinia/medium/ru_RU-irinia-medium.onnx"
        ),
        "piper_config_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "ru/ru_RU/irinia/medium/ru_RU-irinia-medium.onnx.json"
        ),
        "piper_sample_rate": 22050,
        "rtl": False,
        "needs_openai_tts": False,
        "openai_voice": None,
    },
    "zh": {
        "name": "中文",
        "native_name": "中文",
        "flag": "🇨🇳",
        "whisper_code": "zh",
        "deepl_code": "ZH",
        "argos_code": "zh",
        "piper_model": "zh_CN-huayan-x_low",
        "piper_model_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "zh/zh_CN/huayan/x_low/zh_CN-huayan-x_low.onnx"
        ),
        "piper_config_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "zh/zh_CN/huayan/x_low/zh_CN-huayan-x_low.onnx.json"
        ),
        "piper_sample_rate": 22050,
        "rtl": False,
        "needs_openai_tts": False,
        "openai_voice": None,
    },
    "ja": {
        "name": "日本語",
        "native_name": "日本語",
        "flag": "🇯🇵",
        "whisper_code": "ja",
        "deepl_code": "JA",
        "argos_code": "ja",
        "piper_model": None,
        "piper_model_url": None,
        "piper_config_url": None,
        "piper_sample_rate": None,
        "rtl": False,
        "needs_openai_tts": True,
        "openai_voice": "nova",
    },
    "ko": {
        "name": "한국어",
        "native_name": "한국어",
        "flag": "🇰🇷",
        "whisper_code": "ko",
        "deepl_code": "KO",
        "argos_code": "ko",
        "piper_model": None,
        "piper_model_url": None,
        "piper_config_url": None,
        "piper_sample_rate": None,
        "rtl": False,
        "needs_openai_tts": True,
        "openai_voice": "nova",
    },
    "ar": {
        "name": "العربية",
        "native_name": "العربية",
        "flag": "🇸🇦",
        "whisper_code": "ar",
        "deepl_code": "AR",
        "argos_code": "ar",
        "piper_model": None,
        "piper_model_url": None,
        "piper_config_url": None,
        "piper_sample_rate": None,
        "rtl": True,
        "needs_openai_tts": True,
        "openai_voice": "echo",
    },
    "tr": {
        "name": "Türkçe",
        "native_name": "Türkçe",
        "flag": "🇹🇷",
        "whisper_code": "tr",
        "deepl_code": "TR",
        "argos_code": "tr",
        "piper_model": "tr_TR-dfki-medium",
        "piper_model_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "tr/tr_TR/dfki/medium/tr_TR-dfki-medium.onnx"
        ),
        "piper_config_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "tr/tr_TR/dfki/medium/tr_TR-dfki-medium.onnx.json"
        ),
        "piper_sample_rate": 22050,
        "rtl": False,
        "needs_openai_tts": False,
        "openai_voice": None,
    },
    "sv": {
        "name": "Svenska",
        "native_name": "Svenska",
        "flag": "🇸🇪",
        "whisper_code": "sv",
        "deepl_code": "SV",
        "argos_code": "sv",
        "piper_model": "sv_SE-nst-medium",
        "piper_model_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "sv/sv_SE/nst/medium/sv_SE-nst-medium.onnx"
        ),
        "piper_config_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "sv/sv_SE/nst/medium/sv_SE-nst-medium.onnx.json"
        ),
        "piper_sample_rate": 22050,
        "rtl": False,
        "needs_openai_tts": False,
        "openai_voice": None,
    },
    "da": {
        "name": "Dansk",
        "native_name": "Dansk",
        "flag": "🇩🇰",
        "whisper_code": "da",
        "deepl_code": "DA",
        "argos_code": "da",
        "piper_model": "da_DK-talesyntese-medium",
        "piper_model_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "da/da_DK/talesyntese/medium/da_DK-talesyntese-medium.onnx"
        ),
        "piper_config_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "da/da_DK/talesyntese/medium/da_DK-talesyntese-medium.onnx.json"
        ),
        "piper_sample_rate": 22050,
        "rtl": False,
        "needs_openai_tts": False,
        "openai_voice": None,
    },
    "fi": {
        "name": "Suomi",
        "native_name": "Suomi",
        "flag": "🇫🇮",
        "whisper_code": "fi",
        "deepl_code": "FI",
        "argos_code": "fi",
        "piper_model": "fi_FI-harri-medium",
        "piper_model_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "fi/fi_FI/harri/medium/fi_FI-harri-medium.onnx"
        ),
        "piper_config_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "fi/fi_FI/harri/medium/fi_FI-harri-medium.onnx.json"
        ),
        "piper_sample_rate": 22050,
        "rtl": False,
        "needs_openai_tts": False,
        "openai_voice": None,
    },
    "cs": {
        "name": "Čeština",
        "native_name": "Čeština",
        "flag": "🇨🇿",
        "whisper_code": "cs",
        "deepl_code": "CS",
        "argos_code": "cs",
        "piper_model": "cs_CZ-jirka-medium",
        "piper_model_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "cs/cs_CZ/jirka/medium/cs_CZ-jirka-medium.onnx"
        ),
        "piper_config_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "cs/cs_CZ/jirka/medium/cs_CZ-jirka-medium.onnx.json"
        ),
        "piper_sample_rate": 22050,
        "rtl": False,
        "needs_openai_tts": False,
        "openai_voice": None,
    },
    "hu": {
        "name": "Magyar",
        "native_name": "Magyar",
        "flag": "🇭🇺",
        "whisper_code": "hu",
        "deepl_code": "HU",
        "argos_code": "hu",
        "piper_model": "hu_HU-anna-medium",
        "piper_model_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "hu/hu_HU/anna/medium/hu_HU-anna-medium.onnx"
        ),
        "piper_config_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "hu/hu_HU/anna/medium/hu_HU-anna-medium.onnx.json"
        ),
        "piper_sample_rate": 22050,
        "rtl": False,
        "needs_openai_tts": False,
        "openai_voice": None,
    },
    "uk": {
        "name": "Українська",
        "native_name": "Українська",
        "flag": "🇺🇦",
        "whisper_code": "uk",
        "deepl_code": "UK",
        "argos_code": "uk",
        "piper_model": "uk_UA-lada-x_low",
        "piper_model_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "uk/uk_UA/lada/x_low/uk_UA-lada-x_low.onnx"
        ),
        "piper_config_url": (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "uk/uk_UA/lada/x_low/uk_UA-lada-x_low.onnx.json"
        ),
        "piper_sample_rate": 22050,
        "rtl": False,
        "needs_openai_tts": False,
        "openai_voice": None,
    },
}


def get_language(code: str) -> Optional[dict]:
    """Retourne les métadonnées d'une langue par son code ISO 639-1."""
    return LANGUAGE_REGISTRY.get(code)


def get_all_codes() -> list[str]:
    """Retourne la liste de tous les codes de langues supportées."""
    return list(LANGUAGE_REGISTRY.keys())


def get_display_name(code: str) -> str:
    """Retourne le nom natif + drapeau d'une langue."""
    lang = LANGUAGE_REGISTRY.get(code)
    if lang:
        return f"{lang['flag']} {lang['native_name']}"
    return code


def get_argos_pairs() -> list[tuple[str, str]]:
    """
    Retourne toutes les paires de traduction disponibles via ArgosTranslate.
    Exclut les langues sans support Argos.
    """
    supported = [
        code for code, meta in LANGUAGE_REGISTRY.items()
        if meta.get("argos_code")
    ]
    pairs = []
    for src in supported:
        for tgt in supported:
            if src != tgt:
                pairs.append((src, tgt))
    return pairs


def needs_openai_tts(code: str) -> bool:
    """Indique si une langue nécessite OpenAI TTS (pas de modèle Piper)."""
    lang = LANGUAGE_REGISTRY.get(code, {})
    return lang.get("needs_openai_tts", False)


def get_piper_model(code: str) -> Optional[str]:
    """Retourne le nom du modèle Piper pour une langue, ou None si absent."""
    lang = LANGUAGE_REGISTRY.get(code, {})
    return lang.get("piper_model")

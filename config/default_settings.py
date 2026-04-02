#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoxShield — Valeurs de configuration par défaut.
"""

DEFAULT_SETTINGS: dict = {
    "version": "1.0",
    "audio": {
        "input_device_index": None,
        "loopback_device_index": None,
        "virtual_cable_index": None,
        "sample_rate": 16000,
        "chunk_ms": 30,
        "vad_mode": 2,
        "vad_silence_ms": 400,
        "vad_min_speech_ms": 150,
    },
    "stt": {
        "mode": "local",
        "model_size": "tiny",
        "openai_api_key_set": False,
        "language_auto_detect": False,
    },
    "translation": {
        "mode": "local",
        "deepl_api_key_set": False,
        "cache_size": 500,
        "timeout_ms": 3000,
    },
    "tts": {
        "mode": "piper",
        "speed": 1.0,
        "openai_voice": "nova",
        "openai_api_key_set": False,
    },
    "languages": {
        "user_lang": "fr",
        "remote_lang": "en",
    },
    "pipelines": {
        "pipeline_a_enabled": True,
        "pipeline_b_enabled": True,
        "local_tts_output": False,
    },
    "ui": {
        "overlay_position": ["center", "bottom"],
        "overlay_opacity": 0.75,
        "overlay_font_size": 16,
        "overlay_duration_ms": 5000,
        "theme": "dark",
    },
    "hotkeys": {
        "start_stop": "ctrl+shift+t",
        "mute_mic": "ctrl+shift+m",
        "toggle_overlay": "ctrl+shift+s",
        "swap_languages": "ctrl+shift+i",
        "show_hide": "ctrl+shift+l",
    },
    "first_launch": True,
}

# Tailles de modèles Whisper disponibles
WHISPER_MODEL_SIZES = ["tiny", "base", "small", "medium", "large-v3"]

# Modes STT disponibles
STT_MODES = ["local", "api"]

# Modes traduction disponibles
TRANSLATION_MODES = ["local", "deepl", "auto"]

# Modes TTS disponibles
TTS_MODES = ["piper", "openai", "system"]

# Budget latence (ms) par étape — utilisé pour monitoring
LATENCY_BUDGETS = {
    "vad": 10,
    "buffer": 1500,
    "stt": 1000,
    "translation_local": 500,
    "translation_api": 3000,
    "tts": 600,
    "routing": 50,
}

# Virtual Cable — patterns de noms par OS
VIRTUAL_CABLE_PATTERNS = {
    "Windows": ["CABLE Input", "VB-Audio", "VB-Cable"],
    "Darwin": ["BlackHole 2ch", "Soundflower (2ch)", "BlackHole"],
    "Linux": ["pulse", "pipewire"],
}

# Loopback device patterns par OS
LOOPBACK_PATTERNS = {
    "Windows": ["Stereo Mix", "CABLE Output", "Loopback"],
    "Darwin": ["BlackHole", "Soundflower"],
    "Linux": ["monitor"],
}

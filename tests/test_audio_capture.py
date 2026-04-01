#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests unitaires — AudioCapture"""

import pytest
from core.audio_capture import AudioCapture


def test_list_input_devices_returns_list():
    """list_input_devices() retourne toujours une liste."""
    devices = AudioCapture.list_input_devices()
    assert isinstance(devices, list)


def test_list_input_devices_structure():
    """Chaque device a les clés requises."""
    devices = AudioCapture.list_input_devices()
    for dev in devices:
        assert "index" in dev
        assert "name" in dev
        assert "max_input_channels" in dev
        assert dev["max_input_channels"] > 0


def test_list_loopback_devices_returns_list():
    devices = AudioCapture.list_loopback_devices()
    assert isinstance(devices, list)


def test_audio_capture_init():
    cap = AudioCapture(device_index=None, sample_rate=16000, chunk_ms=30)
    assert cap.is_running() is False


def test_chunk_size_calculation():
    cap = AudioCapture(device_index=None, sample_rate=16000, chunk_ms=30)
    assert cap._chunk_frames == 480  # 16000 * 30 / 1000

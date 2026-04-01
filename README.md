# VoxShield

Real-time bidirectional voice translation desktop app — 100% local, no cloud required, <2s latency.

Works with any video conferencing platform (Teams, Zoom, Meet, Discord…) via a Virtual Audio Cable.

---

## How it works

Two parallel audio pipelines run simultaneously:

**Pipeline A — Local → Remote**
```
Microphone → VAD → Whisper STT → ArgosTranslate → Piper TTS → Virtual Cable → Video call
```

**Pipeline B — Remote → Local**
```
System loopback → VAD → Whisper STT → ArgosTranslate → Subtitles overlay
```

---

## Features

- **100% offline** — Whisper (faster-whisper), ArgosTranslate, Piper TTS all run locally
- **<2s end-to-end latency** on modern hardware
- **20 languages** supported out of the box
- **Floating subtitle overlay** — always-on-top, draggable, fade animations
- **Global hotkeys** — start/stop, mute, swap languages, toggle overlay
- **Optional cloud engines** — DeepL API, OpenAI TTS for higher quality
- **Virtual Audio Cable routing** — translated voice appears as a microphone input
- **System tray** — runs in background, quick access menu
- **Secure API key storage** — Windows Credential Manager via keyring

---

## Requirements

- Python 3.10+
- Windows 10/11 (primary), macOS and Linux supported
- [VB-Audio Virtual Cable](https://vb-audio.com/Cable/) (free) for Pipeline A

---

## Installation

### Windows

```bat
install.bat
```

### macOS / Linux

```bash
chmod +x install.sh && ./install.sh
```

The installer will:
1. Create a Python virtual environment
2. Install all dependencies
3. Download the Whisper `base` model
4. Guide you through installing Piper TTS and a Virtual Audio Cable

---

## Quick start

```bash
# Windows
venv\Scripts\python.exe main.py

# macOS / Linux
venv/bin/python main.py
```

On first launch, a setup wizard walks you through microphone selection, language pair, and Virtual Cable configuration.

---

## Default hotkeys

| Action | Shortcut |
|---|---|
| Start / Stop | `Ctrl+Shift+T` |
| Mute mic | `Ctrl+Shift+M` |
| Toggle overlay | `Ctrl+Shift+S` |
| Swap languages | `Ctrl+Shift+I` |
| Show / Hide window | `Ctrl+Shift+L` |

All hotkeys are configurable in Settings.

---

## Project structure

```
voxshield/
├── config/
│   ├── default_settings.py     # Constants and defaults
│   ├── language_registry.py    # 20 languages with metadata
│   └── settings_manager.py     # JSON config + keyring API keys
├── core/
│   ├── audio_capture.py        # Mic and loopback capture (WASAPI resampling)
│   ├── audio_buffer.py         # Thread-safe circular buffer
│   ├── vad_engine.py           # Voice Activity Detection (webrtcvad / Silero)
│   ├── stt_engine.py           # Speech-to-Text (faster-whisper / OpenAI)
│   ├── translation_engine.py   # Translation (ArgosTranslate / DeepL) + LRU cache
│   ├── tts_engine.py           # Text-to-Speech (Piper / OpenAI / system)
│   ├── virtual_audio.py        # Virtual Cable routing
│   └── main_controller.py      # Pipeline orchestrator (6 threads)
├── ui/
│   ├── main_window.py          # PyQt6 main window
│   ├── overlay_window.py       # Floating subtitle overlay
│   ├── settings_window.py      # 5-tab settings dialog
│   ├── system_tray.py          # System tray icon and menu
│   ├── hotkey_manager.py       # Global hotkey registration
│   └── first_launch_wizard.py  # First-run setup wizard
├── utils/
│   ├── logger.py               # Centralized logging
│   ├── audio_utils.py          # RMS, VAD helpers
│   └── platform_utils.py       # OS detection, device discovery
├── tests/                      # 31 unit tests (pytest)
├── main.py                     # Entry point
├── requirements.txt
├── install.bat                 # Windows installer
└── install.sh                  # macOS/Linux installer
```

---

## Supported languages

Arabic, Chinese, Dutch, English, Finnish, French, German, Hindi, Hungarian, Italian, Japanese, Korean, Polish, Portuguese, Romanian, Russian, Spanish, Swedish, Turkish, Ukrainian

---

## Optional: Piper TTS (high quality local voices)

Download the binary from [github.com/rhasspy/piper/releases](https://github.com/rhasspy/piper/releases) and place it in your PATH or configure the path in Settings.

Download voice models (`.onnx`) and place them in:
- Windows: `%APPDATA%\VoxShield\MSIASystems\models\piper\`
- macOS: `~/Library/Application Support/VoxShield/MSIASystems/models/piper/`
- Linux: `~/.config/VoxShield/MSIASystems/models/piper/`

Recommended models: `fr_FR-siwis-medium`, `en_US-lessac-medium`

---

## License

MIT

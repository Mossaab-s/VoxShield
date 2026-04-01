#!/usr/bin/env bash
# VoxShield v1.0 — Script d'installation macOS/Linux
# MSIA Systems — Mars 2026

set -e

echo "============================================================"
echo "  VoxShield v1.0 — Installation macOS/Linux"
echo "  MSIA Systems — Mars 2026"
echo "============================================================"
echo

# ── Détection OS ─────────────────────────────────────────────────────────────
OS=$(uname -s)
echo "[1/8] Système détecté : $OS"

# ── Vérification Python ───────────────────────────────────────────────────────
echo
echo "[2/8] Vérification de Python..."
if ! command -v python3 &> /dev/null; then
    echo "ERREUR : Python 3 non trouvé."
    if [ "$OS" = "Darwin" ]; then
        echo "Installez Python via Homebrew : brew install python@3.11"
    else
        echo "Installez Python 3.11 : sudo apt install python3.11"
    fi
    exit 1
fi

PYVER=$(python3 --version 2>&1 | cut -d' ' -f2)
echo "Python $PYVER trouvé."

# ── Environnement virtuel ─────────────────────────────────────────────────────
echo
echo "[3/8] Création de l'environnement virtuel..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
echo "Environnement virtuel activé."

# ── Installation des dépendances ──────────────────────────────────────────────
echo
echo "[4/8] Installation des dépendances Python..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

if [ "$OS" = "Darwin" ]; then
    echo "Installation dépendances macOS..."
    # Sur macOS, pas de PyAudioWPatch — BlackHole gère le loopback
    pip install -r requirements_macos.txt --quiet 2>/dev/null || true
fi

# ── Piper TTS ─────────────────────────────────────────────────────────────────
echo
echo "[5/8] Installation de Piper TTS..."
PIPER_DIR="venv/piper"
mkdir -p "$PIPER_DIR"

if [ "$OS" = "Darwin" ]; then
    ARCH=$(uname -m)
    if [ "$ARCH" = "arm64" ]; then
        PIPER_URL="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_macos_aarch64.tar.gz"
    else
        PIPER_URL="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_macos_x64.tar.gz"
    fi
else
    PIPER_URL="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz"
fi

if [ ! -f "$PIPER_DIR/piper" ]; then
    echo "Téléchargement Piper TTS..."
    curl -sL "$PIPER_URL" | tar -xz -C "$PIPER_DIR" --strip-components=1 2>/dev/null || \
        echo "AVERTISSEMENT : Téléchargement Piper échoué — installez manuellement depuis GitHub"
    chmod +x "$PIPER_DIR/piper" 2>/dev/null || true
fi

# ── Modèles Piper ─────────────────────────────────────────────────────────────
echo
echo "[6/8] Téléchargement modèles Piper (FR + EN)..."

if [ "$OS" = "Darwin" ]; then
    MODELS_DIR="$HOME/Library/Application Support/VoxShield/MSIASystems/models/piper"
else
    MODELS_DIR="$HOME/.config/VoxShield/MSIASystems/models/piper"
fi
mkdir -p "$MODELS_DIR"

download_model() {
    local name=$1
    local url=$2
    if [ ! -f "$MODELS_DIR/$name.onnx" ]; then
        echo "  Téléchargement $name..."
        curl -sL "$url" -o "$MODELS_DIR/$name.onnx" 2>/dev/null || true
        curl -sL "$url.json" -o "$MODELS_DIR/$name.onnx.json" 2>/dev/null || true
    fi
}

download_model "fr_FR-siwis-medium" \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx"
download_model "en_US-lessac-medium" \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"

# ── ArgosTranslate ────────────────────────────────────────────────────────────
echo
echo "[7/8] Installation ArgosTranslate (fr↔en)..."
python3 -c "
import argostranslate.package, argostranslate.translate
argostranslate.package.update_package_index()
available = argostranslate.package.get_available_packages()
for pair in [('fr','en'), ('en','fr')]:
    pkg = next((p for p in available if p.from_code == pair[0] and p.to_code == pair[1]), None)
    if pkg:
        argostranslate.package.install_from_path(pkg.download())
        print(f'  Paire {pair[0]}→{pair[1]} installée.')
" 2>/dev/null || echo "AVERTISSEMENT : ArgosTranslate sera configuré au premier lancement."

# ── Instructions finales ──────────────────────────────────────────────────────
echo
echo "[8/8] Configuration terminée."
echo
echo "============================================================"
echo "  Installation réussie !"
echo "============================================================"
echo

if [ "$OS" = "Darwin" ]; then
    echo "IMPORTANT — Loopback audio (macOS) :"
    echo "  Installez BlackHole 2ch pour le Pipeline B :"
    echo "  brew install blackhole-2ch"
    echo "  ou : https://existential.audio/blackhole/"
    echo
fi

echo "Pour démarrer VoxShield :"
echo "  source venv/bin/activate && python3 main.py"
echo

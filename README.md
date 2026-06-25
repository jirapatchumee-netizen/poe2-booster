# POE2 Booster

<p align="center">
  <img src="assets/logo.png" alt="POE2 Booster" width="120">
</p>

<p align="center">
  <strong>⚡ One-click performance overlay for Path of Exile 2</strong>
</p>

<p align="center">
  <a href="https://poe2booster.com">Website</a> •
  <a href="https://poe2booster.com/#download">Download</a> •
  <a href="https://poe2booster.com/#pricing">Pro</a>
</p>

---

## What is POE2 Booster?

POE2 Booster is a lightweight overlay tool that fixes the #1 complaint in POE2: **frame rate drops after extended play**. 

It works by:
- 🗑️ **Clearing bloated shader caches** (DirectX, NVIDIA, and AMD caches) to resolve stuttering and frame drops instantly.
- 📊 **Monitoring system performance** (CPU, RAM, GPU temperature) in real-time.

All accessible from an **in-game overlay** — press `F4` to toggle the overlay visibility.

## Features

- 🚀 **One-Click Shader Cache Clear** — click "Boost" to immediately clear DirectX/NVIDIA/AMD shader caches.
- 📊 **Real-Time System Monitor** — monitor CPU, RAM, and GPU Temp directly in-game.
- 🎯 **In-Game Overlay** — persistent minimalist bar that stays on top of your game.
- ⌨️ **Quick Toggle** — press `F4` to hide or show the overlay instantly.
- 👋 **First-Time Wizard** — scans your system and clears bloated cache files on first launch.

## Installation

### Option 1: Installer (Recommended)
1. Download `POE2_Booster_Setup.exe` from [Releases](https://github.com/jirapatchumee-netizen/poe2-booster/releases)
2. Run installer
3. Done! App starts automatically with Windows.

### Option 2: Python (Development)
```bash
# Clone
git clone https://github.com/jirapatchumee-netizen/poe2-booster.git
cd poe2-booster

# Install dependencies
pip install keyboard psutil pystray Pillow

# Run
python src/main.py
```

## Usage

1. **Bar** stays at the top of your screen showing CPU/RAM/GPU stats
2. Press **F4** to expand the full control panel
3. Click **🚀 Boost** for one-click optimization
4. Drag the bar to reposition it

> ⚠️ Set POE2 to **Borderless Windowed** mode for overlay to work.

## Building from Source

```bash
# Install PyInstaller
pip install pyinstaller

# Build .exe
pyinstaller build.spec

# Output: dist/POE2 Booster.exe
```

## System Requirements

- Windows 10/11
- 64MB RAM
- NVIDIA or AMD GPU (for GPU monitoring)

## FAQ

**Is it safe?**  
Yes. It only adjusts Windows settings and clears caches. No game files are modified.

**Will I get banned?**  
No. It doesn't interact with the game process in any way.

## License

MIT License — free to use, modify, and distribute.

---

<p align="center">Made with ⚡ for POE2 players</p>

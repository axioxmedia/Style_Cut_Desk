<div align="center">

# Style Cut Desk

**Packed via Axiox Media**

Local desk app that cuts an image background, then stylizes the cutout from a preset library before exporting a PNG.

<p>
  <a href="docs/README-zh.md"><img src="https://img.shields.io/badge/中文说明-README--zh-e7c07a?style=for-the-badge" alt="Chinese README" /></a>
</p>

<p>
  <a href="#install">Install</a> ·
  <a href="#features">Features</a> ·
  <a href="#requirements">Requirements</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#documentation">FAQ</a>
</p>

<p>
  <img src="https://img.shields.io/badge/platform-Windows_10%2F11-0b0d12?style=flat-square" alt="Windows" />
  <img src="https://img.shields.io/badge/python-3.11%2B-e7c07a?style=flat-square" alt="Python" />
  <img src="https://img.shields.io/badge/ui-zh%20%2F%20en-7ee0c6?style=flat-square" alt="i18n" />
  <img src="https://img.shields.io/badge/pipeline-cutout%20%2B%20presets-c9a227?style=flat-square" alt="pipeline" />
</p>

</div>

<div align="center">
  <img src="docs/APPCap.png" alt="Style Cut Desk preview" width="100%" />
</div>

> [!NOTE]
> This is a new product. It reuses the local cutout pipeline, it does not patch [Image Background Remover](https://github.com/axioxmedia/Image_Background_Remover).
> The first auto cutout may download a rembg / u2net model. After that the app works offline.

> [!WARNING]
> The Windows EXE is unsigned PyInstaller output. SmartScreen may warn on first launch.

---

## At a glance

| Style Cut Desk v1.1 |  |
|---|---|
| **Workflow** | Drop image → normalize PNG → auto / chroma cut → style preset → fill / plate / LUT → Save As PNG |
| **Presets** | White stencil, black stencil, line art, silhouette, color cutout |
| **Export** | Original size, or 512 / 1024 / 2048 / 4096 / 8192. Force-stretch unlocks square upscales such as 569×570 → 1024×1024 |
| **Stack** | FastAPI + static UI + pywebview + PyInstaller |

<a id="install"></a>

## Install

### 1. GitHub Deploy Desk (recommended)

One-click deploy this repository with [GitHub Deploy Desk](https://github.com/axioxmedia/github-deployer).

1. Get the deployer: https://github.com/axioxmedia/github-deployer
2. Paste this repo URL into Deploy Desk: https://github.com/axioxmedia/Style_Cut_Desk
3. Read the README in the app, then confirm deploy.

That is the supported install path. Use the source / EXE steps below only if you are already building from a local checkout.

### 2. Run from source or freeze an EXE

| Path | Command |
|---|---|
| Windows EXE | Double-click `build_exe.bat` → `dist\StyleCutDesk.exe` |
| PowerShell | `powershell -ExecutionPolicy Bypass -File .\build_exe.ps1` |
| Source window | Double-click `start.bat` |

Need Python 3.11 or 3.12 from python.org with **Add python.exe to PATH**.

<a id="features"></a>

## Features

| Feature | Detail |
|---|---|
| Normalize first | JPEG / PNG / WEBP / BMP / GIF first frame / TIFF → 8-bit RGBA PNG |
| Auto cutout | rembg + u2net when available; local edge-flood fallback otherwise |
| Chroma key | Hex color + strength `0.001`–1.0 |
| Preset library | Stylize the cutout after the background is gone |
| Fill | Solid hex or keep transparency |
| Plate / frame | Optional base image with outer padding (canvas edge) and inner padding (frame to icon) |
| LUT | Steel / rust / night / mono / paper wash over non-transparent pixels |
| Export caps | Hide 2048× / 4096× / 8192× when the source long side is smaller unless force-stretch is on |
| Compressed PNG | Optional `optimize` + max compress level |
| Save As | Never overwrites the source file |

<a id="requirements"></a>

## Requirements

| | Minimum | Recommended |
|---|---|---|
| OS | Windows 10 | Windows 11 |
| Python | 3.11 | 3.12 |
| RAM | 8 GB | 16 GB when using rembg on large stills |
| Disk | 500 MB + model cache | SSD |

<a id="architecture"></a>

## Architecture

```
pywebview window
    → 127.0.0.1 FastAPI
        → /api/jobs/normalize
        → /api/jobs/{id}/remove     (bg-remove-chroma)
        → /api/jobs/{id}/style      (image-style-presets)
        → /api/jobs/{id}/export
    → static/index.html + styles.css + app.js
PyInstaller onefile EXE, logs at style_cut_desk.log beside the binary
```

<a id="documentation"></a>

## Documentation

<details>
<summary>How is this different from Image Background Remover?</summary>

BG Key Desk only normalizes and cuts. Style Cut Desk keeps that cutout step, then adds presets, fill, plate padding, LUT, and sized / compressed PNG export. The original GitHub repo is left untouched.

</details>

<details>
<summary>Why do high-resolution export options disappear?</summary>

Caps are 512 / 1024 / 2048 / 4096 / 8192. A cap is listed only when it is less than or equal to the source long side, unless force-stretch is checked. Default is always the current processed canvas at original resolution.

</details>

<details>
<summary>Where is the log if the window fails to open?</summary>

`style_cut_desk.log` next to `StyleCutDesk.exe` (frozen) or next to `app.py` (source).

</details>

## License

Packed via Axiox Media · [axiox.media](https://axiox.media)

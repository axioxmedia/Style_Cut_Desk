<div align="center">

# 风格抠图台

**由安溯媒体打包**

本地桌面工具：先抠掉背景，再从预设库风格化透明件，最后按尺寸导出 PNG。

<p>
  <a href="../README.md"><img src="https://img.shields.io/badge/English-README-7ee0c6?style=for-the-badge" alt="English README" /></a>
</p>

<p>
  <a href="#install">安装</a> ·
  <a href="#features">功能</a> ·
  <a href="#requirements">环境</a> ·
  <a href="#architecture">结构</a> ·
  <a href="#documentation">问答</a>
</p>

<p>
  <img src="https://img.shields.io/badge/platform-Windows_10%2F11-0b0d12?style=flat-square" alt="Windows" />
  <img src="https://img.shields.io/badge/python-3.11%2B-e7c07a?style=flat-square" alt="Python" />
  <img src="https://img.shields.io/badge/ui-zh%20%2F%20en-7ee0c6?style=flat-square" alt="i18n" />
  <img src="https://img.shields.io/badge/pipeline-cutout%20%2B%20presets-c9a227?style=flat-square" alt="pipeline" />
</p>

</div>

<div align="center">
  <img src="APPCap.png" alt="风格抠图台 预览" width="100%" />
</div>

> [!NOTE]
> 这是独立新产品。它复用本地抠底流程，不会改 [Image Background Remover](https://github.com/axioxmedia/Image_Background_Remover) 仓库。
> 第一次 Auto 抠底可能会下载 rembg / u2net 模型，之后可离线使用。

> [!WARNING]
> Windows EXE 是未签名的 PyInstaller 产物，首次打开可能被 SmartScreen 拦截。

---

## 一览

| 风格抠图台 v1.0 |  |
|---|---|
| **流程** | 拖入原图 → 规范成 PNG → Auto / 色键抠底 → 套预设 → 填色 / 底图 / LUT → 另存 PNG |
| **预设** | 白线黑底模板、黑线白底模板、线稿、单色剪影、保留原色透明件 |
| **导出** | 默认原尺寸；可选 512 / 1024 / 2048 / 4096 / 8192。勾选强制拉升后可把 569×570 拉成 1024×1024 |
| **技术栈** | FastAPI + 静态界面 + pywebview + PyInstaller |

<a id="install"></a>

## 安装

### 1. GitHub Deploy Desk（推荐）

用 [GitHub Deploy Desk](https://github.com/axioxmedia/github-deployer) 一键部署本仓库。

1. 先装部署器：https://github.com/axioxmedia/github-deployer
2. 把仓库地址贴进 Deploy Desk：https://github.com/axioxmedia/Style_Cut_Desk
3. 在应用里读完说明后再确认部署。

这是正路。只有你已经在本地检出源码时，才走下面的 EXE / 源码步骤。

### 2. 源码运行或打 EXE

| 方式 | 命令 |
|---|---|
| Windows EXE | 双击 `build_exe.bat` → `dist\StyleCutDesk.exe` |
| PowerShell | `powershell -ExecutionPolicy Bypass -File .\build_exe.ps1` |
| 源码窗口 | 双击 `start.bat` |

需要 python.org 的 Python 3.11 或 3.12，并勾选 **Add python.exe to PATH**。

<a id="features"></a>

## 功能

| 功能 | 说明 |
|---|---|
| 先规范化 | JPEG / PNG / WEBP / BMP / GIF 首帧 / TIFF → 8 位 RGBA PNG |
| Auto 抠底 | 能加载 rembg + u2net 就用模型；否则走本地边缘洪水填充 |
| 色键 | 十六进制颜色 + 强度 `0.001`–`1.0` |
| 预设库 | 背景去掉之后再风格化 |
| 填充 | 纯色或保持透明 |
| 底图边框 | 可选底图，外 padding 管图边距，内 padding 管框与图标间距 |
| LUT | 钢青 / 锈橙 / 夜青 / 单色 / 图纸，作用在非透明像素 |
| 导出档位 | 原图长边不够大时不显示更高分辨率 |
| 压缩 PNG | 可选 optimize + 最高压缩等级 |
| 另存为 | 绝不覆盖原图 |

<a id="requirements"></a>

## 环境

| | 最低 | 建议 |
|---|---|---|
| 系统 | Windows 10 | Windows 11 |
| Python | 3.11 | 3.12 |
| 内存 | 8 GB | 处理大图 + rembg 时 16 GB |
| 磁盘 | 500 MB + 模型缓存 | SSD |

<a id="architecture"></a>

## 结构

```
pywebview 窗口
    → 127.0.0.1 FastAPI
        → /api/jobs/normalize
        → /api/jobs/{id}/remove     (bg-remove-chroma)
        → /api/jobs/{id}/style      (image-style-presets)
        → /api/jobs/{id}/export
    → static/index.html + styles.css + app.js
PyInstaller 单文件 EXE，日志写在可执行文件旁的 style_cut_desk.log
```

<a id="documentation"></a>

## 问答

<details>
<summary>和 Image Background Remover 有什么关系？</summary>

BG Key Desk 只做规范化和抠底。风格抠图台保留这一步，再往上加预设、填色、底图 padding、LUT，以及按尺寸 / 压缩导出。原仓库不会被改写。

</details>

<details>
<summary>为什么有的分辨率选项不见了？</summary>

档位是 512 / 1024 / 2048 / 4096 / 8192。只有不超过原图长边的档才会出现。默认永远是当前画布的原始分辨率。

</details>

<details>
<summary>窗口打不开时日志在哪？</summary>

冻结后看 `StyleCutDesk.exe` 旁边的 `style_cut_desk.log`；源码运行则在 `app.py` 同目录。

</details>

Packed via Axiox Media · [axiox.media](https://axiox.media)

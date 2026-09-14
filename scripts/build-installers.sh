#!/usr/bin/env bash
# 圣经讲义桌面安装包 · 跨平台独立构建脚本
#
# 用途：在两个独立的原生平台上分别打包，两个安装包默认连接线上数据库
#       (39.102.143.118:3306, 库/用户均为 bible_library)，无需用户手动配置。
#
# 原理：backend/scripts/package_backend.py 在打包时会读取项目根目录 .env 中的
#       BIBLE_DB_* 字段，把完整的线上数据库连接（含密码）写入后端 bundle 的
#       内置 .env（运行时位于 sys._MEIPASS/.env）。安装后首次启动即自动连线上库。
#
# 重要：本机（Intel x86_64 macOS）无法生成 macOS arm64 与 Windows 安装包，
#       必须在对应原生平台上运行本脚本的相应段落。
#
# ─────────────────────────────────────────────────────────────
# 通用前置（两种平台都需先准备）：
#   - Node.js 22.12+ 、uv 0.12.5 、Python 3.14.6
#   - 项目根目录存在 .env，且 BIBLE_DB_PASSWORD 为真实线上库密码
#     （可 cp .env.example .env 后填写）
# ─────────────────────────────────────────────────────────────

set -euo pipefail

# =========================
# 1) macOS ARM64（Apple Silicon）
#    在本机为 Apple Silicon (M 系列) 的 Mac 上执行
# =========================
build_mac_arm64() {
  cd "$(dirname "$0")/.."
  npm ci
  # package:mac:native = build + package:backend(PyInstaller) + electron-builder
  # --arm64 让 Electron 与 PyInstaller 后端均为 arm64（必须在 Apple Silicon 上运行）
  # 带 .env 构建时，package_backend.py 自动把线上库账号密码嵌入安装包
  npm run package:mac:native -- --arm64 --config.directories.output=release/mac-arm64
  # 产物： release/mac-arm64/圣经讲义-0.1.0-mac-arm64.dmg

  # （可选）本机 ad-hoc 重签名 + 校验内置 .env（CI 凭据无关产物走 finalize-internal-mac.py）
  # python3 scripts/finalize-internal-mac.py \
  #   release/mac-arm64/圣经讲义-0.1.0-mac-arm64.dmg \
  #   release/internal/圣经讲义-0.1.0-mac-arm64-internal.dmg --arch arm64
}

# =========================
# 2) Windows 11 x64
#    在 Windows 11 (x64) 上以 PowerShell 执行以下等价步骤：
# =========================
#   cd <项目根目录>
#   Copy-Item .env.example .env        # 填写真实 BIBLE_DB_PASSWORD
#   npm ci
#   $env:BIBLE_BUILD_ARCH="x64"       # 让 package-backend.cjs 选用 64 位后端工程
#   npm run package:win -- --x64      # = build + package:backend + electron-builder --win nsis
#   # 产物： release/圣经讲义-0.1.0-windows-x64-setup.exe
#   说明：Windows 端当前没有与 finalize-internal-mac.py 等价的“注入凭据”脚本；
#         直接在本机带 .env 构建即可把线上库密码嵌入安装包，无需手动配置。

# =========================
# 3) 安全 CI 路径（凭据不入制品）
#    .github/workflows/build-desktop.yml 用 BIBLE_CREDENTIAL_FREE_BUILD=1 构建，
#    产物不含密码。下载 mac-arm64 DMG 后，在本地用 finalize 注入 .env 并重新签名：
#      python3 scripts/finalize-internal-mac.py <下载的mac-arm64.dmg> \
#        release/internal/圣经讲义-0.1.0-mac-arm64-internal.dmg --arch arm64
#    Windows x64 如需凭据内置，请在 Windows 机器上带 .env 直接构建（见段落 2）。
# =========================

case "${1:-mac}" in
  mac)  build_mac_arm64 ;;
  *)    echo "用法: $0 mac   (Windows 请在 Windows 11 上按脚本内 PowerShell 段落执行)" >&2; exit 1 ;;
esac

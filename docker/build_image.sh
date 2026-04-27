#!/bin/bash
# ============================================================
# Mango 基础镜像构建脚本（包含Python依赖与Allure环境）
# ============================================================
# 用法: ./docker/build_image.sh [版本号]
# 示例: ./docker/build_image.sh v3.6.0
# ============================================================

set -euo pipefail

VERSION="${1:-v3.6.0}"
IMAGE_NAME="mango"
FULL_IMAGE_NAME="${IMAGE_NAME}:${VERSION}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKERFILE_PATH="docker/image/dockerfile"

echo "============================================================"
echo "🥭 Mango 基础镜像构建"
echo "============================================================"
echo "📦 镜像名称: ${FULL_IMAGE_NAME}"
echo "📄 Dockerfile: ${DOCKERFILE_PATH}"
echo "📁 项目目录: ${PROJECT_ROOT}"
echo "============================================================"

cd "$PROJECT_ROOT"

if [ ! -f "$DOCKERFILE_PATH" ]; then
    echo "❌ 错误: ${DOCKERFILE_PATH} 不存在"
    exit 1
fi

if [ ! -d "plugins/allure-2.32.2" ]; then
    echo "❌ 错误: plugins/allure-2.32.2 不存在"
    echo "💡 请确认 Allure 目录已放在 plugins 下"
    exit 1
fi

echo "🔨 开始构建基础镜像..."
docker build \
    --network=host \
    -t "$FULL_IMAGE_NAME" \
    -f "$DOCKERFILE_PATH" \
    .

echo "============================================================"
echo "✅ 基础镜像构建成功: ${FULL_IMAGE_NAME}"
echo "============================================================"

#!/bin/bash
# ============================================================
# Mango 整体镜像构建脚本（集成框架代码）
# ============================================================
# 用法: ./docker/build_whole.sh [版本号]
# 示例: ./docker/build_whole.sh v3.6.0
# ============================================================

set -euo pipefail

VERSION="${1:-v3.6.0}"
BASE_IMAGE="mango:${VERSION}"
IMAGE_NAME="mango-app"
FULL_IMAGE_NAME="${IMAGE_NAME}:${VERSION}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKERFILE_PATH="docker/whole/Dockerfile"

echo "============================================================"
echo "🥭 Mango 整体镜像构建"
echo "============================================================"
echo "📦 目标镜像: ${FULL_IMAGE_NAME}"
echo "🧱 基础镜像: ${BASE_IMAGE}"
echo "📄 Dockerfile: ${DOCKERFILE_PATH}"
echo "📁 项目目录: ${PROJECT_ROOT}"
echo "============================================================"

cd "$PROJECT_ROOT"

if [ ! -f "$DOCKERFILE_PATH" ]; then
    echo "❌ 错误: ${DOCKERFILE_PATH} 不存在"
    exit 1
fi

if ! docker image inspect "$BASE_IMAGE" > /dev/null 2>&1; then
    echo "❌ 错误: 基础镜像 ${BASE_IMAGE} 不存在"
    echo "💡 请先执行: ./docker/build_image.sh ${VERSION}"
    exit 1
fi

echo "🔨 开始构建整体镜像..."
docker build \
    --network=host \
    -t "$FULL_IMAGE_NAME" \
    -f "$DOCKERFILE_PATH" \
    --build-arg BASE_IMAGE="$BASE_IMAGE" \
    --build-arg BUILD_DATE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
    --build-arg VERSION="$VERSION" \
    .

echo "============================================================"
echo "✅ 整体镜像构建成功: ${FULL_IMAGE_NAME}"
echo "============================================================"
echo "💡 运行示例: python3 docker/whole/Run_Docker.py --help"

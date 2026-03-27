#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"
ENV_FILE="$DEPLOY_DIR/.env"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker 未安装，无法启动 MentorDB 生产环境。" >&2
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  cp "$DEPLOY_DIR/.env.example" "$ENV_FILE"
  echo "已生成 deploy/.env，请先检查数据库路径、LLM 配置和端口。"
fi

mkdir -p "$DEPLOY_DIR/data"

cd "$DEPLOY_DIR"
docker compose --env-file "$ENV_FILE" up -d --build

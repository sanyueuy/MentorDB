#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API_HOST="${MENTORDB_DEV_API_HOST:-127.0.0.1}"
API_PORT="${MENTORDB_DEV_API_PORT:-8000}"
WEB_PORT="${MENTORDB_DEV_WEB_PORT:-3000}"
DB_URL="${MENTOR_INDEX_DATABASE_URL:-sqlite+pysqlite:///./zju_three_schools_deep.db}"

if [ ! -d "$ROOT_DIR/.venv" ]; then
  echo ".venv 不存在，请先在项目根目录创建虚拟环境并安装依赖。" >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm 未安装，无法启动 WebUI。" >&2
  exit 1
fi

cd "$ROOT_DIR"

cleanup() {
  if [ -n "${API_PID:-}" ] && kill -0 "$API_PID" >/dev/null 2>&1; then
    kill "$API_PID" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

. "$ROOT_DIR/.venv/bin/activate"
export MENTOR_INDEX_DATABASE_URL="$DB_URL"
export NEXT_PUBLIC_MENTORDB_API_BASE_URL="http://$API_HOST:$API_PORT"

mentor-index serve-api --host "$API_HOST" --port "$API_PORT" &
API_PID=$!

echo "MentorDB API 已启动: http://$API_HOST:$API_PORT"
echo "MentorDB WebUI 即将启动: http://127.0.0.1:$WEB_PORT"

cd "$ROOT_DIR/web"
npm run dev -- --hostname 0.0.0.0 --port "$WEB_PORT"

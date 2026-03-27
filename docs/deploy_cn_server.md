# MentorDB 中国服务器部署

## 目标

这一套部署面向中国大陆云服务器，默认交付为：

- `FastAPI` API
- `Next.js` WebUI
- `Nginx` 反向代理

统一入口是：

```bash
./scripts/deploy.sh
```

或者直接：

```bash
cd deploy
cp .env.example .env
docker compose --env-file .env up -d --build
```

## 目录说明

- [`deploy/docker-compose.yml`](/Users/wuhong/Documents/保研资料/mentor-index/deploy/docker-compose.yml)
- [`deploy/api.Dockerfile`](/Users/wuhong/Documents/保研资料/mentor-index/deploy/api.Dockerfile)
- [`deploy/web.Dockerfile`](/Users/wuhong/Documents/保研资料/mentor-index/deploy/web.Dockerfile)
- [`deploy/nginx.conf`](/Users/wuhong/Documents/保研资料/mentor-index/deploy/nginx.conf)
- [`deploy/.env.example`](/Users/wuhong/Documents/保研资料/mentor-index/deploy/.env.example)

## 上线前准备

1. 把数据库文件放到 `deploy/data/`，或者把 `MENTOR_INDEX_DATABASE_URL` 改成你自己的 Postgres / SQLite 地址。
2. 检查 `deploy/.env` 里的 embedding、LLM 和端口配置。
3. 如果你要通过中国大陆云服务器的正式域名对外提供服务，先完成备案；在备案完成前，更适合先用服务器 IP、测试域名或仅内网方式验证。

## 默认环境变量

- `MENTOR_INDEX_DATABASE_URL`
- `MENTOR_INDEX_EMBEDDING_BACKEND`
- `MENTOR_INDEX_EMBEDDING_MODEL`
- `MENTOR_INDEX_EMBEDDING_DEVICE`
- `MENTOR_INDEX_LLM_BASE_URL`
- `MENTOR_INDEX_LLM_API_KEY`
- `MENTOR_INDEX_LLM_MODEL`
- `MENTORDB_API_BASE_URL`
- `NEXT_PUBLIC_MENTORDB_API_BASE_URL`
- `MENTORDB_HTTP_PORT`

## 生产建议

- Apple Silicon 本地开发可继续使用 `MPS`；Linux 服务器默认先用 `cpu`，确认驱动后再切换。
- WebUI 和 API 统一从 `Nginx` 暴露，便于后续接 HTTPS 和 CDN。
- 如果后续要挂域名，建议在 Nginx 外再接证书和域名解析，不要把测试 IP 当作正式公开入口。

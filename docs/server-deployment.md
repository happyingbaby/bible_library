# 线上 API 部署

## 运行拓扑

- 域名：`https://library.fdeline.com`
- Nginx：宝塔安装的 Nginx，监听 80/443；80 跳转 HTTPS，443 反代 `127.0.0.1:8765`
- API：Docker 中的 Python 3.14 + FastAPI/Uvicorn，使用 host 网络且只监听服务器回环地址
- 数据库：服务器本机 MySQL 5.7.40，容器通过 `127.0.0.1:3306` 访问
- 文件：`/www/wwwroot/bible-library/data` 持久化原件、待确认文件和备份

## 首次部署

1. 将仓库内容放到 `/www/wwwroot/bible-library`。
2. 在 `deploy/.env` 写入 `BIBLE_DB_USER`、`BIBLE_DB_PASSWORD`、`BIBLE_DB_NAME`；文件权限设为 `0600`。`BIBLE_DB_HOST` 和端口由 Compose 固定为服务器本机地址。
3. 执行 `docker compose -f deploy/docker-compose.yml build api`。
4. 执行 `docker compose -f deploy/docker-compose.yml up -d api`。
5. 将 `deploy/library.fdeline.com.nginx.conf` 安装为宝塔 Nginx 站点配置，签发并安装 `library.fdeline.com` 证书后重载 Nginx。

## 更新与回滚

1. 更新代码后重新执行 `docker compose -f deploy/docker-compose.yml build api`。
2. 执行 `docker compose -f deploy/docker-compose.yml up -d api`；数据卷不会随容器替换。
3. 验证 `curl https://library.fdeline.com/api/status`、容器日志和登录流程。
4. 回滚时用上一版本镜像重新创建容器；数据库迁移可能不可逆，升级前必须生成应用完整备份和数据库备份。

## 客户端适配范围

- `frontend/src/api.ts` 中所有 `api()` 与 `download()` 请求固定使用 `https://library.fdeline.com/api`。
- Electron 不再启动本机 Python 服务，不再生成或传递 `X-App-Key`，安装包不再包含后端和数据库凭据。
- 登录、用户、讲义、历史、导入导出、回收站、经文、备份与恢复继续使用原路由，仅传输位置由本机 API 改为线上 API。
- 服务端数据库连接仅由 `deploy/.env` 管理；线上禁用 `/api/connection`，客户端数据库连接表单已移除。
- `file://` Electron 页面通过 CORS 的 `null` 来源访问；线上同域页面允许 `https://library.fdeline.com`，本机 5173/5174 仍用于开发验证。

# 圣经讲义管理平台

个人本机使用的 macOS 桌面应用。Electron + React + TypeScript，FastAPI + MySQL。管理员整理讲义、添加用户；阅读用户查看已发布讲义并点击经文引用。

## 当前机器直接使用

应用位于 `release/mac/圣经讲义.app`。双击打开，首次进入创建管理员页面；管理员创建后，在「用户管理」添加阅读用户。

当前连接配置已改为远程 MySQL `39.102.143.118:3306`，数据库和用户名均为 `bible_library`。密码仅保存在本机配置文件中。此次检查端口返回“拒绝连接”，尚未验证认证或初始化远程库；服务器恢复可访问后需重启应用。远程数据库模式需要网络连接，原始导入文件仍保存在本机。原本 Docker 数据库未迁移或删除，旧连接备份为同目录下的 `database.previous.json`。

连接配置、原始文件和恢复前安全备份位于：

```text
~/Library/Application Support/圣经讲义/library/
├── database.json       # 本机 MySQL 配置，权限 0600，不加入项目或完整备份
├── originals/          # 导入原件
├── pending/            # 待确认的讲义导入
├── scripture_pending/  # 待确认的译本导入
└── backups/            # 恢复前自动备份
```

没有默认正式管理员或内置正式经文。首次管理员由使用者自行设置。初始密码至少 6 位；添加用户后首次登录必须改密码。测试账户只存在于 `/private/tmp` 的隔离预览数据库中。

## 使用流程

1. 登录后导入 `.docx` 或 UTF-8 `.md`，核对预览和转换报告，确认后保存为未发布讲义。
2. 点击「编辑」，维护 Markdown、标题、分类、标签。保存后更新引用索引并记录历史；「历史版本」可恢复之前内容。
3. 在「管理」中发布，阅读用户即可看到。取消发布或移入回收站后，列表、搜索和详情接口均不可访问。
4. 管理员从「经文数据」导入 JSON，先核对差异，再确认。更新同一个 `code` 会整体替换该译本，包括删除新文件中未提供的经节。
5. 点击 `【创1:1】` 等引用，抽屉选择中英文译本对照。`上`、`a` 等半节标记保留，但展示完整经节。
6. 使用「备份与恢复」导出 ZIP。恢复前先生成安全备份；恢复后使用备份中的账户重新登录。

`examples/` 包含示例讲义和两个**明确标注的占位测试译本**，不是正式圣经文字，不自动导入正式资料库。

## 项目目录

前端和后端分别集中在两个文件夹，根目录保留联合启动与桌面打包配置。所有 npm 命令仍在项目根目录执行，JavaScript 依赖统一通过根目录的 `package.json` 和锁文件管理。

```text
frontend/               # React 前端
├── src/                # 页面、样式和 API 客户端
├── index.html
├── vite.config.ts      # 开发服务器与构建配置
├── tsconfig.json       # TypeScript 配置
└── dist/               # 前端构建产物
backend/                # Python 后端
├── app/                # API、业务和数据模型
├── migrations/         # 数据库迁移
├── tests/              # 隔离回归测试
├── scripts/            # 打包、预览和数据库验证工具
├── launcher.py
├── pyproject.toml      # 运行依赖、测试及打包依赖组
├── uv.lock             # uv 生成的精确版本与校验哈希
└── .python-version     # 开发 Python 版本
desktop/                # Electron 桌面外壳
scripts/                # 联合启动、本机网页网关及其测试
package.json            # 统一命令、JS 依赖与桌面打包配置
```

`npm run dev:frontend` 单独启动前端开发服务器；`npm run dev` 联合启动前端和 Electron 管理的后端。隔离界面验证时，在两个终端分别执行 `uv run --project backend --locked python backend/scripts/preview_backend.py` 和 `VITE_APP_KEY=bible-local-preview-key npm run dev:frontend`，并先确认未继承正式 `DATABASE_URL`。

浏览器使用 `npm run web` → `http://127.0.0.1:5173/`；桌面开发使用 `npm run dev` → Electron 窗口（Vite 内部地址为 `http://127.0.0.1:5174/`）。两种模式可同时运行，共用正式资料库。浏览器不要直接打开桌面 Vite 地址；隔离前端预览也使用 5174，需与桌面开发交替运行。

## 安装和开发

桌面端构建目标为 macOS 通用版（Intel x64 + Apple Silicon arm64）和 Windows x64/32 位版。安装包尚未 Apple Developer 或 Microsoft 代码签名；首次运行时系统可能显示安全确认。

开发需要 Node.js（建议 22.12+）、uv、Python 3.14+ 和 MySQL（本机验证版本为 8.4）。当前机器使用 Node 20.20.2、Python 3.14.6 完成构建；electron-builder 的间接依赖会对 Node 20 给出引擎版本提示。

```bash
uv sync --project backend --locked
npm ci
npm run dev
```

Electron 启动并管理 Python 服务，不需另开后端终端。开发和安装版默认使用同一个应用资料目录。

先按 [uv 官方说明](https://docs.astral.sh/uv/getting-started/installation/) 安装 uv。项目通过 `backend/.python-version` 选择 Python 3.14.6，缺失时 uv 会下载对应解释器。虚拟环境统一位于 `backend/.venv`；旧根目录 `.venv` 不再使用，可自行清理。依赖源沿用中科大 PyPI 镜像并在项目中明确配置。

`npm run dev`、`npm run desktop`、`npm run web` 启动前自动执行 `npm run sync:backend`，使用 `--locked` 校验锁文件。桌面和网页启动器直接调用 uv 管理的 Python，确保退出时能终止后端。安装版仍使用独立打包服务，无需 uv。

依赖维护（根目录执行，提交 `pyproject.toml` 和 `uv.lock`）：

```bash
uv add --project backend 包名
uv add --project backend --dev 测试工具名
uv add --project backend --group build 打包工具名
uv lock --project backend --upgrade-package 包名
npm run test:backend
```

默认同步运行和测试依赖；`npm run package:backend` 自动启用 `build` 组。仅需运行依赖时可使用 `uv sync --project backend --locked --no-dev`。原 requirements 文件已移除；若外部工具需要该格式，使用 `uv export --project backend --locked --all-groups --format requirements-txt --output-file /tmp/bible-requirements.txt` 临时导出。

构建：

```bash
npm run build
npm run package:mac
npm run package:win
```

`package:mac` 和 `package:win` 构建当前操作系统与 CPU 架构的原生安装包。完整的四架构产物由 GitHub Actions 的 `Build desktop clients` 工作流生成：

- `圣经讲义-0.1.0-mac-universal.dmg` / `.zip`：同一个应用兼容 Intel 与 Apple Silicon。
- `圣经讲义-0.1.0-windows-x64-setup.exe`：Windows 64 位安装程序。
- `圣经讲义-0.1.0-windows-ia32-setup.exe`：Windows 32 位安装程序，也可运行在 64 位 Windows。

64 位客户端会将 Python、Pandoc、数据库驱动与迁移一起打包。Windows 32 位客户端因现代 Pandoc 和 `cryptography` 已停止提供 x86 二进制包，使用独立锁定依赖和内置 DOCX 兼容转换器；它支持常见标题、段落、粗体、斜体和列表，复杂表格、图片及修订会在导入预览中提示人工核对。MySQL 保持独立运行。

## 后端与数据

- `backend/app/modules/`：账户、讲义导入编辑、引用解析、译本、备份等业务模块。
- `backend/app/models.py`：SQLAlchemy 数据模型；`database.py` 管理连接和事务；`security.py` 统一认证、权限和会话撤销。
- `backend/migrations/`：Alembic 迁移，启动时执行。首版为 `0001`；以后修改模型必须添加独立迁移，不通过修改旧版本升级已有库。
- Markdown 正文和历史仅以 MySQL 内容为权威来源；导出 `.md` 是副本，不做文件双向同步。
- 本地服务随机端口，只监听 `127.0.0.1`。Electron 每次启动生成进程访问密钥；用户身份用 12 小时有效的随机会话 token，数据库只保存 token 摘要。
- 所有资料操作必须通过后端角色检查；密码使用 Argon2id；停用、密码重置和恢复备份撤销会话。
- Markdown 禁止原始 HTML；代码和已有链接中的引用不转为经文按钮；外部图片不自动加载。

主要接口统一位于 `/api`：账户 `/setup`、`/login`、`/me`、`/users`、`/password`；讲义 `/lectures`、`/imports/preview`、`/imports/confirm`；经文 `/translations`、`/translations/preview`、`/translations/confirm`、`/verses`；备份 `/backups`、`/backups/preview`、`/backups/restore`。

译本 JSON：

```json
{
  "code": "demo-zh",
  "name": "测试中文（非正式经文）",
  "language": "zh",
  "source": "人工占位测试数据",
  "verses": [
    { "book": "Gen", "chapter": 1, "verse": 1, "text": "测试占位文字" }
  ]
}
```

`book` 支持 66 卷的规范 ID 或已配置中文名称/简称，使用 `/api/books` 查询规范列表。每个译本的 `(book, chapter, verse)` 唯一。编号间隙会报告；不会推断整本译本是否完整，也不自动对齐不同分节体系。

## 验证

```bash
npm run test:backend
npm run build
```

测试覆盖首次改密、阅读权限、停用与重置撤销会话、最后管理员保护、六种引用、代码排除、Word 实际转换及超范围提示、导入确认、历史恢复、冲突保存、译本差异、缺节显示、备份往返和损坏备份拒绝。

`MYSQL_TEST_URL` 可交给 `backend/scripts/mysql_smoke.py`，必须指向全新、可丢弃且名称包含 `bible_test` 的数据库。`backend/scripts/run_docker_mysql_test.py` 针对本机现有容器创建随机测试库和账户，完成后只清理本次测试资源。

浏览器界面测试使用 `backend/scripts/preview_backend.py`，只读写 `/private/tmp` 隔离数据；前端需以 `VITE_APP_KEY=bible-local-preview-key` 启动 Vite。`backend/scripts/seed_preview.py` 写入测试样例。正式桌面应用不使用这个固定测试密钥或 SQLite。

## 本机网页版

在项目根目录运行 `npm run web`，然后在本机浏览器访问 `http://127.0.0.1:5173`。关闭启动进程会停止网页服务；重新运行该命令即可再次使用。

网页版使用 `~/Library/Application Support/圣经讲义/library/` 的现有数据库配置和原件，与桌面版共用正式账户和资料。`DATABASE_URL`、`BIBLE_DATA_DIR` 可覆盖默认配置，启动前请核实。启动后端会执行已有 Alembic 迁移。远程 MySQL 需要网络连接。

网页版仅监听 `127.0.0.1`，不是可供其他电脑访问的服务器部署。启动器生成临时应用密钥，账户和权限校验仍由后端执行。网页与 API 同源，下载使用浏览器保存流程。`npm run web` 使用 5173，桌面开发及隔离前端预览使用 5174。网页版可与桌面开发同时运行。

## 首版边界

- Word 的普通正文、标题、列表、加粗与顺序已验证；复杂表格、图片、脚注、修订等提示人工核对，保留原件。不会把不支持的复杂内容称为无损转换。
- 不支持 PDF/OCR、旧 `.doc`、跨章引用、多人协作、云同步或逐讲义授权。
- 不抓取在线网站；确定经文来源后可增加独立采集器，经统一导入校验后入库。
- 登录与数据权限用于本机应用内隔离，不阻止拥有操作系统或 MySQL 管理权限的人直接访问数据。
- 完整备份包含密码哈希及私人讲义，需自行妥善保存；当前提供手动备份，未实现自动定期备份。

## 经文目录与爬虫开发

经文管理页面支持两约、书卷、章节浏览和逐节维护。字段解释、关联约束及采集程序写入示例见 [圣经数据结构与爬虫接口](docs/圣经数据结构与爬虫接口.md)。本次新增迁移为 `0002`，独立采集器用法见上述文档第 11 节；管理页不提供 JSON 导入入口，既有后端导入接口保留兼容。

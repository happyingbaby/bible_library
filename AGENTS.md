# 圣经讲义管理平台

## 1. 项目目标与适用范围

- 本文件适用于当前项目根目录及其子目录，记录已确认的长期设计和开发约束。
- 项目是使用托管 API 的跨平台桌面讲义资料库，当前应用版本为 `0.1.0`；下一次迭代从 2026-09-14、`main` 的 `c3f567c` 基线开始，下一版本号尚未确定。
- 核心流程：管理员添加用户 → Word 转 Markdown → 整理与编辑 → 发布 → 用户阅读 → 点击引用查看中英文经文。
- 管理员维护同一个资料库，阅读用户查看全部已发布讲义；不做逐用户、逐讲义授权。
- 已实现用户管理、导入预览与进度反馈、Markdown 编辑、作者与讲道日期、历史恢复、发布、回收站、经文目录与逐节维护、经文对照、关键词检索、关联讲义抽屉及完整备份恢复。
- 当前生产拓扑为 Electron 客户端 → `https://library.fdeline.com/api` → 服务器 FastAPI → MySQL；客户端不再启动 Python、不直连 MySQL，也不保存数据库凭据。
- 生产 API 和原始文件集中在服务器，因此不同客户端读取同一资料库；这仍不是多人实时协作，没有实时编辑、锁定或合并机制。
- 托管模式必须联网；离线使用和客户端本地资料库已不属于当前生产能力。
- 不把计划、测试占位数据或未经验证的功能写成正式交付能力。

## 2. 技术栈与版本

以下为本次开发环境和锁文件中已核实的版本；更新依赖时同步更新锁文件。

- Python 依赖管理：uv `0.12.5`（本机验证）；使用 `backend/pyproject.toml` 与 `backend/uv.lock`。
- 开发运行时：Node.js `20.20.2`、Python `3.14.6`；本机已验证 MySQL `8.4.11`。
- 前端：React / React DOM `19.3.0`、TypeScript `5.9.3`、Vite `6.4.3`。
- 桌面：Electron `40.10.2`、electron-builder `26.15.3`。
- 图标：lucide-react `0.468.0`。
- API：FastAPI `0.141.1`、Uvicorn `0.52.4`、Pydantic `2.13.5`。
- 数据：SQLAlchemy `2.0.52`、PyMySQL `1.2.0`、Alembic `1.19.2`。
- 文档：pypandoc_binary `1.17`、markdown-it-py `4.2.0`。
- 密码：argon2-cffi `25.1.0`；仓库仍保留 PyInstaller `6.22.2` 的旧后端打包工具，但当前托管 API 客户端不使用它。
- 测试：pytest `9.1.1`、httpx `0.28.1`。
- JS 精确版本以 `package-lock.json` 为准；Python 精确版本以 `backend/uv.lock` 为准。
- `backend/win32/` 和独立锁文件属于旧 Windows 32 位本地后端交付链，当前生产构建不使用；不要在未重新决策前继续维护或发布该目标。
- `backend/pyproject.toml` 记录运行依赖及 `dev`（测试）、`build`（旧打包工具）依赖组；`backend/uv.lock` 由 uv 生成，不手工编辑。
- Node 20 已完成构建，但部分打包依赖声明要求 Node `22.12+`；切换运行时后重新验证构建。
- 远程 MySQL 的实际版本：MySQL5.7.40；不得把本机 MySQL 的版本当成远程版本。

## 3. 安装、运行、测试与构建

所有命令均在项目根目录执行。先安装 uv；`backend/.python-version` 固定后端开发 Python 版本，虚拟环境为 `backend/.venv`。`npm run dev` 的前置脚本仍会以 `--locked` 同步后端依赖，但当前桌面客户端本身只包含 Electron 前端。

```bash
uv sync --project backend --locked
npm ci
npm run dev
```

- `npm run dev` 启动 `127.0.0.1:5174` 的 Vite 和 Electron；Electron 不启动本机后端，前端直接访问线上 API。
- `npm run desktop` 只启动 Electron，要求 5174 已有 Vite；生产数据操作会写线上资料库，开发调试不得使用破坏性数据。
- `npm run web` 仍保留旧本机网关实现，但当前 `frontend/src/api.ts` 使用绝对线上 API 地址，不能再把该命令描述为完整的本地后端隔离方案；新迭代若保留网页版，应先统一其运行模式。
- CORS 当前允许生产域名、`127.0.0.1:5173`、`127.0.0.1:5174` 和 Electron 的 `null` 来源；修改客户端来源时同步更新 `backend/app/main.py` 并运行 `backend/tests/test_cors.py`。
- 后端业务验证优先运行隔离 pytest；需要手工启动本机后端时，必须显式使用测试数据库和测试资料目录，不能指向生产 MySQL。

```bash
npm run test:backend
npm run test:dev
npm run test:web
npm run build
npm run package:mac
npm run package:win
```

- `test:backend` 通过 `uv run --project backend --locked` 执行 pytest，使用临时 SQLite 数据库；导入路径由 `backend/pyproject.toml` 配置。
- `test:dev` 验证 Vite 端口冲突时不启动 Electron、Electron 启动失败时释放端口。
- `build` 先执行 TypeScript 检查，再生成 `frontend/dist/`。
- `package:mac` 和 `package:win` 只重新构建前端并由 electron-builder 生成轻量客户端；生产安装包不得再包含 Python、Pandoc、迁移或数据库凭据。
- `.github/workflows/build-desktop.yml` 当前仅构建 Apple Silicon arm64 DMG 与 Windows x64 NSIS；过去的 Intel Mac、Windows 32 位和通用包属于旧直连架构，不是当前发布目标。
- 2026-09-14 已静态验证 macOS ARM64 和 Windows x64 安装包的目标架构、线上 API 地址及不含后端；尚未在目标设备完成安装登录验收。
- 两个平台均未做受信任的商业代码签名；macOS 没有 Developer ID 公证，Windows 可能出现 SmartScreen 提示。

隔离预览必须显式指定测试 `DATABASE_URL` 和 `BIBLE_DATA_DIR` 后启动 `backend/scripts/preview_backend.py`，再用 `VITE_API_BASE=/api VITE_APP_KEY=bible-local-preview-key npm run dev:frontend` 启动前端。Vite 将 `/api` 代理到本机 8765；开发变量仅在 DEV 模式生效，生产构建仍固定使用线上 API。

## 4. 核心目录与职责

- `desktop/main.cjs`：桌面窗口、单实例、导出文件保存及退出流程；不再管理 Python 子进程。
- `desktop/preload.cjs`：向渲染层暴露有限的 IPC 能力。
- `frontend/src/main.tsx`：登录、讲义、编辑器、抽屉和管理窗口；目前主要界面集中在此文件。
- `frontend/src/api.ts`：固定线上 API 基址、HTTP 请求、内存会话 token、导出与共享类型。
- `frontend/src/ScriptureSearch.tsx`、`ScriptureSearch.css`：经文关键词检索、高亮结果和关联讲义全文抽屉。
- `frontend/src/style.css`：桌面布局及视觉样式；`frontend/index.html` 包含 CSP。
- `backend/launcher.py`：Uvicorn 启动入口。
- `backend/app/main.py`：路由注册、本地应用密钥检查、连接配置及状态接口。
- `backend/app/database.py`：连接创建、迁移执行、会话工厂和事务依赖。
- `backend/app/models.py`：账户、会话、讲义、历史、引用、译本与经文等 SQLAlchemy 模型。
- `backend/app/security.py`：密码哈希、认证依赖、角色检查、token 摘要和会话撤销。
- `backend/app/modules/accounts.py`：初始化、登录、用户管理、密码和账户状态。
- `backend/app/modules/lectures.py`：导入转换、正文管理、发布、回收站、历史与原件导出。
- `backend/app/modules/references.py`：66 卷映射、经文引用解析、Markdown 渲染。
- `backend/app/modules/scripture.py`：译本预览确认、差异校验和经节查询。
- `backend/app/modules/backups.py`：备份生成、验证、预览及恢复。
- `backend/app/collectors/lxfyt.py`、`backend/scripts/crawl_scripture.py`：来源限定的网站采集器与命令行入口。
- `backend/migrations/`：Alembic 迁移；当前版本链为 `0001` → `0002`（两约／书卷／章节目录）→ `0003`（作者与讲道日期）→ `0004`（个人批注，尚未部署生产）。
- `backend/app/modules/annotations.py`、`paragraphs.py` 和 `frontend/src/Annotations.tsx`：个人批注权限、段落绑定及批注工作区；说明见 `docs/个人批注.md`。
- `backend/tests/`：隔离测试夹具及核心业务回归。
- `frontend/vite.config.ts`、`frontend/tsconfig.json`：前端构建与类型检查配置。
- `backend/scripts/`：后端打包、隔离预览、Docker 数据库初始化与集成验证脚本。
- `deploy/`：生产 Docker、Nginx 和线上服务配置；操作说明见 `docs/server-deployment.md`。
- `scripts/`：桌面开发、本机网页网关及旧内部安装包封装脚本；不得把旧直连数据库封装流程用于当前托管 API 客户端。
- `examples/`：示例讲义和明确标注的中英文测试占位译本。
- `frontend/dist/`、`backend/build/`、`backend/dist/`、`release/`：构建产物，不作为手工修改的源码。

## 5. 架构、部署与数据位置

- 当前生产链路为 Electron/React 客户端 → `https://library.fdeline.com/api` → 宝塔 Nginx → `127.0.0.1:8765` 的 Docker FastAPI → MySQL 5.7.40。
- API 容器使用 host 网络、`restart: unless-stopped`；Nginx 负责 80 到 443 跳转、TLS 和反向代理，证书读取宝塔 ACME 续期目录。
- 服务端代码位于 `/www/wwwroot/bible-library`，资料目录为 `/www/wwwroot/bible-library/data`；`originals/`、`pending/`、`scripture_pending/`、`restore_pending/` 和 `backups/` 均为服务器数据，不再属于客户端应用目录。
- 服务器数据库配置只保存在 `/www/wwwroot/bible-library/deploy/.env`，权限必须为 `0600`；生产设置 `BIBLE_REQUIRE_APP_KEY=0`、`BIBLE_ALLOW_CONNECTION_CONFIG=0`，禁止客户端调用 `/api/connection` 改库。
- Markdown 正文和历史以 MySQL 为权威来源；原始 Word 保存在服务器用于核对，不做数据库正文与外部 `.md` 的双向同步。
- 客户端固定使用 HTTPS API，不读取 `BIBLE_DB_*`、不保存数据库密码、不发送 `X-App-Key`；账户认证仍使用 Bearer token。
- 后端仍支持 `DATABASE_URL`、`BIBLE_ENV_FILE`、`BIBLE_DATA_DIR`、`BIBLE_APP_KEY` 等本地测试配置，但这些是服务端／开发入口，不是生产客户端配置能力。
- FastAPI 启动会执行 Alembic 升级；生产部署不是只读动作，升级前必须同时保留应用完整备份和数据库备份。
- 旧本机 MySQL、`database.previous.json`、根目录 `.env` 和含数据库配置的旧内部安装包只用于历史追溯，不代表当前生产链路，也不得重新分发。

## 6. 核心业务规则及理由

### 账户与权限

- 固定 `admin`、`reader` 两种角色，避免首版引入不必要的细粒度权限体系。
- 首次初始化创建管理员；不提供公开注册，不内置正式管理员密码。
- 初始化认证成功后前端必须同步 `status.initialized=true`，确保退出后使用 `/login` 而不是再次调用 `/setup`。
- 用户名按小写存储并唯一；新增或重置密码后的用户必须先修改初始密码。
- 密码长度为 6～128 个字符，保存 Argon2id 哈希；不能从数据库还原明文密码。
- 用户只能停用，不能永久删除；不能停用最后一个启用的管理员。
- 登录 token 有效期为 12 小时；数据库只存 SHA-256 摘要，前端 token 保存在内存。
- 停用、重置密码、修改密码和恢复备份必须撤销相应旧会话。
- 权限由后端认证依赖强制检查，不能只通过隐藏前端按钮实现限制。
- 阅读用户只能查看已发布且未删除的讲义；列表、搜索、详情均执行相同过滤。
- 阅读用户不能管理用户、编辑或导出讲义、导入经文或执行备份恢复。

### 讲义导入、编辑与发布

- 导入采用“预览 → 人工核对 → 确认保存”，防止转换问题直接进入正式资料库。
- 支持 `.docx` 和 UTF-8 `.md`；旧 `.doc` 必须先转换为 `.docx`。
- 保证常见正文、标题、列表、加粗和顺序；遇到复杂内容必须报告，不能宣称无损转换。
- 原始文件、转换报告和 Markdown 一并保留；重新导入默认生成新讲义，避免覆盖编辑成果。
- 讲义具有 `author`（最多 100 字）和可空的 `sermon_date`；两项随讲义、历史、导入确认和备份恢复一起保存，未填日期不能回退显示更新时间。
- 文件解析期间必须显示进度／忙碌反馈并防止重复提交，长转换不能表现为界面卡死。
- 新讲义默认未发布；发布后，阅读用户查看最新保存版本。
- 删除进入回收站并取消发布；恢复后仍未发布，管理员需再次发布。
- 保存携带 `revision`，过期版本返回冲突，不能静默覆盖更新。
- 每次保存写入历史；历史恢复创建新版本，保留恢复前内容。
- 保存或恢复正文时更新引用索引，避免索引与正文脱节。
- 退出或切换编辑内容时保留未保存提醒。

### 经文引用与译本

- 支持 `【创1:1】`、`【创1:1-3】`、`【创1:1-5上】` 及对应圆括号、`a` 标记形式。
- 使用规则和书卷别名解析，不依赖 AI；统一处理中英文标点与常见空格。
- 半节标记保留在引用记录中，抽屉展示完整经节，避免推断半节边界。
- 第一版仅支持单章内单节和连续范围；未知书卷、非法范围必须明确提示，不猜测。
- 可点击引用仅在渲染结果中生成，不能改写 Markdown 原文。
- 行内代码、代码块、已有链接内的引用不自动转为按钮。
- 译本经节以“译本＋书卷＋章＋节”唯一定位；缺失时显示缺失，不自动替换译本。
- 译本导入先检查重复、空文本、编号及差异，确认后才写入。
- 相同 `code` 的导入是整体替换；差异必须包括新增、修改和删除，并检测预览版本冲突。
- 缺节检查只判断已提供章节内的编号间隙，不推断全书完整性或译本分节对应。
- `examples/` 经文是占位测试文字，不能作为正式圣经译本分发或自动导入。
- 固定目录为旧约 39 卷、新约 27 卷，共 66 卷、1,189 章；`0002` 只初始化目录，不插入正式经文正文。
- 经文管理页按两约 → 书卷 → 章节 → 经节浏览，支持译本创建、逐节新增／修改／删除和 revision 冲突保护；固定目录本身没有增删改接口。
- 关键词检索覆盖全部已录入译本，按字面子串匹配并转义 SQL 通配符；结果显示译本、完整卷名、章、节并高亮关键词，每页默认 100 条、最多 200 条。
- 点击检索结果按当前引用索引反查包含该节的讲义全文；范围和半节引用按包含关系匹配，同一讲义重复引用只返回一次，管理员可见未删除讲义，阅读用户仍只见已发布且未删除讲义。
- `lxfyt` 采集器已实现来源域名限制、robots 检查、限速、结构校验、HTML 缓存、断点续跑和经 API 写入；只验证过真实创世记第 1 章及隔离写入，未执行全站正式入库，不能把采集器存在写成正式译本已交付。

### 安全与备份

- 个人批注由会话绑定用户，管理员也无权通过批注接口查看或修改他人的批注。原段落改写或重复匹配无法确认时保留笔记并提示定位失效，不猜测跳转。
- 个人批注不进入管理员可下载的资料备份；数据库存在批注时阻止应用内整库恢复，避免账户归属错配。完整批注灾备依赖服务器数据库备份，尚无个人批注导出导入。

- 生产 FastAPI 在服务器只监听 `127.0.0.1:8765`，公网只暴露 Nginx 的 HTTPS；不得把 Uvicorn 端口或 MySQL 端口作为客户端 API 暴露。
- Electron 保持 `contextIsolation: true`、`nodeIntegration: false`、`sandbox: true`。
- 桌面端保留受限 IPC 和 CSP，外部网页交由系统浏览器处理；`X-App-Key` 仅为本地后端兼容机制，当前生产客户端和线上 API 不使用它。
- Markdown 禁止原始 HTML，外部图片不自动加载，减少导入内容执行脚本或联网的风险。
- 完整备份包含账户哈希、讲义、历史、引用、译本、经文及原件，不包含会话或数据库连接密码。
- 恢复前校验版本、路径、关联和原件，并自动备份当前资料；不能直接解压不可信 ZIP 路径。
- 恢复使用事务替换数据库，原件采用新文件名写入，失败时回滚并清理新文件。
- 恢复成功清除旧会话和待确认导入；使用备份中的账户重新登录。

## 7. 开发约定与验收

- 每次修改完成并通过相关验证后，必须创建本地 Git 提交，并报告提交哈希；不提交敏感配置、资料库数据或构建产物，未经要求不推送远程。

- Python 延续现有模块与函数命名方式，API 数据字段沿用 `snake_case`；前端保持 TypeScript 类型检查。
- 新接口统一使用 `/api` 前缀、Pydantic 输入校验和现有认证依赖。
- 客户端当前编译期固定 API 基址；改动路由、认证、CORS 或响应结构时必须同时验证已发布客户端兼容性，不能只验证浏览器源码。
- 数据库操作沿用 SQLAlchemy 与现有事务机制，不绕过讲义可见性和角色检查。
- 修改模型必须添加独立 Alembic 迁移；不能修改旧迁移来升级已存在的数据库。
- 不手改构建产物；源码变化后重新构建，需要交付桌面更新时重新打包。
- `.venv/`、`node_modules/`、缓存、构建目录及本机配置不能当作项目源码提交。
- 格式化工具、额外 lint 规则、分支与提交规范：[待补充]；不得声称已有未配置的工具链。
- 权限、数据转换、持久化及恢复行为变化必须有相应回归验证。
- 2026-09-14 最近一次托管 API 交付验证为 71 项后端测试、TypeScript/Vite 构建、线上 `/api/status`、HTTPS 跳转、CORS、连接配置禁用，以及 macOS ARM64／Windows x64 安装包静态架构检查；修改后重新跑相关检查，测试数量以实际 pytest 收集结果为准。
- SQLite 测试不替代 MySQL 验证；涉及事务、字符集、迁移和恢复时使用可丢弃的 MySQL 测试库。
- `backend/scripts/mysql_smoke.py` 仅能指向全新、可丢弃且库名包含 `bible_test` 的数据库。
- `backend/scripts/run_docker_mysql_test.py` 绑定既有本机容器并创建随机测试库，完成后删除本次测试库与账户。
- 不把这些初始化、恢复或清理测试指向正式远程数据库。
- 生产部署变更还必须核对 `docker compose ps`、容器重启次数、服务端回环监听、Nginx 配置、TLS 和一次认证流程；状态接口成功不能替代登录与业务接口验收。

## 8. 已知限制与接手易错点

- `README.md` 仍混有“本机后端、客户端直连 MySQL、四架构安装包”等旧说明；在新迭代更新 README 前，以本文件、`frontend/src/api.ts` 和 `docs/server-deployment.md` 为准。
- `scripts/web.cjs`、本地预览脚本、数据库连接页面的后端兼容代码和内部直连安装包封装脚本尚未完全清理；不要误判它们仍是生产入口。
- 生产 API 基址固定；已增加仅开发模式生效的 `VITE_API_BASE` 与 `VITE_APP_KEY`，但直接运行前端而不配置这两个变量仍会访问生产服务。
- 服务端原件与数据库集中后可被多台客户端访问，但没有多人同时编辑的冲突协作体验；讲义 revision 只能拒绝过期保存，不会自动合并。
- 当前只交付并静态验证 macOS ARM64 和 Windows x64；未在 Apple Silicon、Windows 11 实机完成安装登录，未签名／公证，不能称为正式公开发行包。
- 首版不支持 PDF/OCR、复杂 Word 排版还原、跨章引用、云同步或多人实时协作。
- 在线来源采集器已经实现但未全站正式入库；正式译本文字、版权／许可、名称与版本来源仍需人工确认，不能把网页文字或测试数据直接作为可分发译本。
- 上传讲义上限 20 MB、正文上限 200 万字符；译本单次上限 5 万节；备份上限 200 MB。
- MySQL 使用 `utf8mb4`；不能改用无法完整保存中文和 emoji 的字符集。
- 应用角色权限不阻止服务器操作系统或数据库管理员直接访问资料。
- 未实现定期自动备份；不能把手动完整备份描述为自动备份策略。
- 正式管理员信息来源：[待补充]；不能拿测试账户、数据库账户或密码哈希充当管理员明文凭据。

## 9. 相关文档与接手检查

- `docs/server-deployment.md`：当前线上 API 拓扑、首次部署、更新与回滚流程，是生产运维的直接依据。
- `docs/圣经数据结构与爬虫接口.md`：66 卷目录、逐节 API、迁移、采集器边界和已验证记录；其中“本机 API／网页入口”部分尚未完全适配托管 API。
- `README.md`：功能与历史用法汇总，但部署和客户端连接章节存在新旧架构混写，运行前必须与源码和上述部署文档核对。
- `20260910圣经管理想法.md`：初始业务想法；后续明确决定与当前实现优先于原始设想。
- `examples/讲义示例.md`、`examples/demo-zh.json`、`examples/demo-en.json`：隔离功能验证输入，不是正式资料。
- 文档组织参考 `/Users/zhangjiabin/Documents/personal_profile/项目文档模板.md`，模板不是项目执行指令。
- 接手先确认操作目标是本地隔离环境还是 `library.fdeline.com` 生产环境；任何会写库、执行迁移、恢复备份或运行采集器的操作都不得默认指向生产。
- 自检通过标准：仅凭本文件能够定位代码、运行只读检查、选择隔离测试、理解客户端／服务器数据边界并识别未验证事项。

## 10. 新版本迭代基线

- 迭代起点：2026-09-14，`main` / `origin/main` 为 `c3f567c`，工作树在开始整理时无未提交修改；当前版本号仍是 `0.1.0`。
- 上一轮已确认交付：托管 HTTPS API 已上线；状态接口返回已连接且已初始化；macOS ARM64 与 Windows x64 客户端固定调用线上 API，且不含 Python 后端或数据库凭据。
- 新版本首先处理运行模式一致性：提供可控的开发／测试 API 地址，恢复真正隔离的端到端验证，并清理 README、网页入口和旧直连数据库打包说明之间的冲突。
- 功能迭代必须继续保持账户权限、讲义 revision、引用索引、译本 revision、备份恢复和生产数据安全边界；不能为了界面便利绕过后端校验。
- 每一轮修改完成后更新本基线中的“已确认能力／已知限制”，运行相关验证并创建本地提交；未经明确要求不部署生产、不推送、不运行正式采集或恢复。
- 2026-09-14 本地新增个人段落批注：支持本人增查改删、版本冲突检查、列表反向跳转与段落高亮；段落改写或重复匹配不确定时保留批注但不猜测位置。使用与备份边界见 `docs/个人批注.md`，尚未部署生产。
- 本轮已通过 76 项隔离后端测试及 TypeScript／Vite 构建，隔离浏览器已验证新增、编辑和反向导航。2026-09-14 本机 MySQL 8.4.11 和独立 MySQL 5.7.40 集成验证均通过，覆盖旧库迁移至 `0004`、utf8mb4、引用索引、批注增查改删与版本冲突、备份恢复和会话撤销；5.7.40 补查了批注定位及存在批注时的恢复保护。临时数据库、账户及独立测试容器已清理。隔离兼容性验证不代表生产已部署或完成线上验收。
- MySQL 5.7.40 可复跑 `backend/.venv/bin/python backend/scripts/run_mysql57_test.py`：固定官方 `mysql:5.7.40` 的 amd64 镜像，创建随机容器、随机回环端口及临时数据目录，结束时仅删除本次容器与数据；不复用生产数据库或既有 MySQL 容器。

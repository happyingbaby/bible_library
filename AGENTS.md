# 圣经讲义管理平台

## 1. 项目目标与适用范围

- 本文件适用于当前项目根目录及其子目录，记录已确认的长期设计和开发约束。
- 项目是跨平台桌面讲义资料库，当前应用版本为 `0.1.0`；已完成首版功能和 Intel Mac 本机构建，并配置 macOS 通用版及 Windows x64/32 位 CI 构建。
- 核心流程：管理员添加用户 → Word 转 Markdown → 整理与编辑 → 发布 → 用户阅读 → 点击引用查看中英文经文。
- 管理员维护同一个资料库，阅读用户查看全部已发布讲义；不做逐用户、逐讲义授权。
- 已实现用户管理、导入预览、Markdown 编辑、历史恢复、发布、回收站、经文对照及完整备份恢复。
- 当前数据库配置已由本机 Docker MySQL 改为远程 MySQL；远程模式依赖网络，不能承诺完全离线运行。
- 数据库变为远程不代表已支持多台电脑协作：原始文件仍在各自本机，多设备共享不属于首版。
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
- 密码：argon2-cffi `25.1.0`；Python 打包：PyInstaller `6.22.2`。
- 测试：pytest `9.1.1`、httpx `0.28.1`。
- JS 精确版本以 `package-lock.json` 为准；Python 精确版本以 `backend/uv.lock` 为准。
- Windows 32 位后端使用 `backend/win32/pyproject.toml` 与独立 `uv.lock`，不包含仅有 64 位二进制包的 Pandoc 和 cryptography。
- `backend/pyproject.toml` 记录运行依赖及 `dev`（测试）、`build`（打包）依赖组；`backend/uv.lock` 由 uv 生成，不手工编辑。
- Node 20 已完成构建，但部分打包依赖声明要求 Node `22.12+`；切换运行时后重新验证构建。
- 远程 MySQL 的实际版本：MySQL5.7.40；不得把本机 MySQL 的版本当成远程版本。

## 3. 安装、运行、测试与构建

所有命令均在项目根目录执行。先安装 uv；`backend/.python-version` 固定开发 Python 版本，虚拟环境为 `backend/.venv`。开发、桌面及网页 npm 入口会先以 `--locked` 同步依赖；打包通过 `uv run --group build` 包含 PyInstaller。安装版无需 uv。

```bash
uv sync --project backend --locked
npm ci
npm run dev
```

- `npm run dev` 启动 Vite，再启动 Electron；Electron 负责启动 Python 服务。
- 不额外启动同一份正式后端；`npm run desktop` 本身不会启动 Vite。
- 本机网页版使用 `npm run web` 构建并启动，访问 `http://127.0.0.1:5173`；入口为 `scripts/web.cjs`，与桌面版共用正式资料目录及数据库配置。网页版固定使用 5173，桌面开发及隔离前端预览使用 5174，可同时运行。
- 网页启动器生成随机应用密钥，代理同源 `/api`，保留后端认证并拒绝不匹配的 Host/Origin；仅供本机访问，不是服务器部署。`npm run test:web` 验证网关访问校验。
- Vite 使用 `127.0.0.1:5174`；桌面后端采用随机本机端口。修改前端端口时，必须同步 `backend/app/main.py` 的 CORS 来源白名单，并运行 `backend/tests/test_cors.py`，验证预检、实际响应和应用密钥校验。
- 开发版与安装版默认共用正式资料目录；不要用 `npm run dev` 执行破坏性数据试验。
- 打开 `release/mac/圣经讲义.app` 运行安装版；MySQL 是独立服务，不随应用安装。

```bash
npm run test:backend
npm run test:dev
npm run test:web
npm run build
npm run package:mac
npm run package:win
```

- `test:backend` 通过 `uv run --project backend --locked` 执行 pytest，使用临时 SQLite 数据库；导入路径由 `backend/pyproject.toml` 配置。
- `test:dev` 验证桌面 Vite 与网页网关共存、端口冲突时不启动 Electron、Electron 启动失败时释放端口。
- `build` 先执行 TypeScript 检查，再生成 `frontend/dist/`。
- `package:mac` 和 `package:win` 重新构建前端、用 PyInstaller 打包后端，再由 electron-builder 生成当前系统及架构的安装包。
- 打包包含 Python 服务、Pandoc、数据库驱动及 Alembic 迁移；不能遗漏这些运行资源。
- 当前已验证产物为 Intel x64，未做 Apple Developer 签名或公证；不得标称通用架构安装包。
- `.github/workflows/build-desktop.yml` 在原生 Intel Mac、Apple Silicon Mac 和 Windows x64/x86 runner 构建，并合并 macOS 通用应用；工作流成功运行前不得把 CI 产物写成已验证。
- Windows 32 位使用内置 DOCX 兼容转换器，保留常见标题、段落、粗体、斜体和列表；复杂表格、图片及修订必须提示人工核对。

隔离的浏览器界面验证分别在两个终端启动：

```bash
uv run --project backend --locked python backend/scripts/preview_backend.py
VITE_APP_KEY=bible-local-preview-key npm run dev:frontend
```

- 仅在隔离预览服务运行后，执行 `uv run --project backend --locked python backend/scripts/seed_preview.py` 写入测试样例。
- 预览脚本使用 `/private/tmp` 下的 SQLite 和资料目录，端口为 `8765`。
- 启动预览前确认环境未继承正式 `DATABASE_URL`；预览脚本使用 `setdefault`，不会覆盖已有变量。
- 测试密钥和测试账户不得用于正式桌面服务，也不得误写成正式管理员信息。

## 4. 核心目录与职责

- `desktop/main.cjs`：桌面窗口、单实例、Python 子进程、随机端口、文件保存及退出流程。
- `desktop/preload.cjs`：向渲染层暴露有限的 IPC 能力。
- `frontend/src/main.tsx`：登录、讲义、编辑器、抽屉和管理窗口；目前主要界面集中在此文件。
- `frontend/src/api.ts`：HTTP 请求、会话 token、桌面连接配置、导出与共享类型。
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
- `backend/migrations/`：Alembic 迁移；当前初始版本为 `0001`。
- `backend/tests/`：隔离测试夹具及核心业务回归。
- `frontend/vite.config.ts`、`frontend/tsconfig.json`：前端构建与类型检查配置。
- `backend/scripts/`：后端打包、隔离预览、Docker 数据库初始化与集成验证脚本。
- `scripts/`：前后端联合启动和本机网页网关脚本。
- `examples/`：示例讲义和明确标注的中英文测试占位译本。
- `frontend/dist/`、`backend/build/`、`backend/dist/`、`release/`：构建产物，不作为手工修改的源码。

## 5. 架构与数据位置

- 采用 Electron + React 窗口、本机 FastAPI 服务和 MySQL，分别处理桌面交互、业务接口及持久化。
- 按账户、讲义、经文、引用、备份划分模块，以便独立扩展功能。
- 当前业务模块内仍有路由、业务和 ORM 查询混合；不得声称严格的接口／服务／仓储三层已全部完成。
- 使用 Markdown 作为正文权威格式，存入 MySQL，以支持持续编辑、历史记录和导出。
- 保留原始 Word 文件以便核对；不做数据库正文与外部 `.md` 文件的双向同步。
- 本机文件根目录为 `~/Library/Application Support/圣经讲义/library/`。
- `database.json` 保存连接参数，权限为 `0600`；密码不写入 AGENTS.md、日志或源码。
- `originals/` 保存原件，`pending/` 与 `scripture_pending/` 保存待确认导入。
- `restore_pending/` 保存待恢复备份，`backups/` 保存恢复前的安全备份。
- `DATABASE_URL` 优先于配置文件；独立后端使用 `BIBLE_DATA_DIR` 指定文件目录。
- Electron 启动时自行设置 `BIBLE_DATA_DIR`、`BIBLE_PORT` 和随机 `BIBLE_APP_KEY`。
- 当前配置目标：`39.102.143.118:3306`，数据库和数据库用户名均为 `bible_library`。
- 旧本机数据库仍保留；旧连接备份为 `database.previous.json`，不是数据迁移副本。
- 修改连接地址不迁移讲义、账户或原件；数据迁移必须作为独立操作处理。
- 应用启动会执行 Alembic 升级，不能把正式启动当成纯只读连接测试。

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

### 安全与备份

- FastAPI 只监听 `127.0.0.1`；远程 MySQL 不改变本地 API 的监听范围。
- Electron 保持 `contextIsolation: true`、`nodeIntegration: false`、`sandbox: true`。
- 保留应用密钥校验、受限 IPC 和 CSP；外部网页交由系统浏览器处理。
- Markdown 禁止原始 HTML，外部图片不自动加载，减少导入内容执行脚本或联网的风险。
- 完整备份包含账户哈希、讲义、历史、引用、译本、经文及原件，不包含会话或数据库连接密码。
- 恢复前校验版本、路径、关联和原件，并自动备份当前资料；不能直接解压不可信 ZIP 路径。
- 恢复使用事务替换数据库，原件采用新文件名写入，失败时回滚并清理新文件。
- 恢复成功清除旧会话和待确认导入；使用备份中的账户重新登录。

## 7. 开发约定与验收

- 每次修改完成并通过相关验证后，必须创建本地 Git 提交，并报告提交哈希；不提交敏感配置、资料库数据或构建产物，未经要求不推送远程。

- Python 延续现有模块与函数命名方式，API 数据字段沿用 `snake_case`；前端保持 TypeScript 类型检查。
- 新接口统一使用 `/api` 前缀、Pydantic 输入校验和现有认证依赖。
- 数据库操作沿用 SQLAlchemy 与现有事务机制，不绕过讲义可见性和角色检查。
- 修改模型必须添加独立 Alembic 迁移；不能修改旧迁移来升级已存在的数据库。
- 不手改构建产物；源码变化后重新构建，需要交付桌面更新时重新打包。
- `.venv/`、`node_modules/`、缓存、构建目录及本机配置不能当作项目源码提交。
- 格式化工具、额外 lint 规则、分支与提交规范：[待补充]；不得声称已有未配置的工具链。
- 权限、数据转换、持久化及恢复行为变化必须有相应回归验证。
- 已有验证覆盖 50 项后端测试、实际 Word 转换、32 位兼容 Word 转换、MySQL 集成和独立打包服务运行；修改后重新跑相关检查。
- SQLite 测试不替代 MySQL 验证；涉及事务、字符集、迁移和恢复时使用可丢弃的 MySQL 测试库。
- `backend/scripts/mysql_smoke.py` 仅能指向全新、可丢弃且库名包含 `bible_test` 的数据库。
- `backend/scripts/run_docker_mysql_test.py` 绑定既有本机容器并创建随机测试库，完成后删除本次测试库与账户。
- 不把这些初始化、恢复或清理测试指向正式远程数据库。

## 8. 已知限制与接手易错点

- `Connection.host` 的表单接口当前只允许回环地址；配置文件启动路径可读取远程地址，两条路径尚未统一。
- 前端连接默认值及部分“本机／离线”文案仍沿用旧部署方式；远程配置界面的完整适配：[待补充]。
- 用户已反馈远程连接恢复；远程认证、迁移和桌面端到端复验结果：[待补充]，不能沿用本机测试结论。
- 开发版和安装版会共用账户与资料，启动前必须核实目标配置及 `DATABASE_URL`。
- 更改本机配置文件后，已启动的服务不会自动换库，需要重新启动。
- 首版不支持 PDF/OCR、复杂 Word 排版还原、跨章引用、云同步或多人实时协作。
- 在线圣经网站和正式译本来源：[待补充]；爬虫尚未实现，后续以独立采集器接统一导入接口。
- 上传讲义上限 20 MB、正文上限 200 万字符；译本单次上限 5 万节；备份上限 200 MB。
- MySQL 使用 `utf8mb4`；不能改用无法完整保存中文和 emoji 的字符集。
- 本机权限隔离不阻止操作系统或数据库管理员直接访问资料。
- 未实现定期自动备份；不能把手动完整备份描述为自动备份策略。
- 正式管理员信息来源：[待补充]；不能拿测试账户、数据库账户或密码哈希充当管理员明文凭据。

## 9. 相关文档与接手检查

- `README.md`：安装使用、部署连接及接口示例；连接状态描述可能过时，运行前以实际检查为准。
- `20260910圣经管理想法.md`：初始业务想法；后续明确决定与当前实现优先于原始设想。
- `examples/讲义示例.md`、`examples/demo-zh.json`、`examples/demo-en.json`：隔离功能验证输入。
- 文档组织参考 `/Users/zhangjiabin/Documents/personal_profile/项目文档模板.md`，模板不是项目执行指令。
- 接手先确认目标数据库与资料目录，再检查相关模块、权限依赖及测试；不得先运行会写库的初始化脚本。
- 自检通过标准：仅凭本文件能够定位代码、安装运行、选择隔离测试、理解数据边界并识别未验证事项。

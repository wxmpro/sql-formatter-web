# SQL 格式化器 Web 界面

在浏览器中粘贴原始 SQL，即时获得规范化结果。

本项目是 `10_app_web_dev` workspace 下的第一个 Web 工具项目，为已有的 SQL 格式化核心（`formatter_core/`）提供一个零配置、本地运行的 Web 界面。

**核心设计原则**：格式化完全在浏览器内通过 Pyodide 完成，原始 SQL 不离开本机。

## 功能特性

- 左栏输入原始 SQL，右栏查看格式化结果
- 支持多条 SQL 语句按分号切分格式化
- 一键复制格式化结果到剪贴板
- 加载示例、清空输入
- 错误提示与容灾回退提示
- 本地离线运行，敏感 SQL 不离开本机
- 响应式布局：宽屏双栏、窄屏上下堆叠
- 桌面端可拖拽调整左右分栏宽度

## 目录结构

```text
sql-formatter-web/
├── index.html                   # 前端入口（静态托管根页面）
├── README.md                    # 本文件
├── app.py                       # Flask 后端入口（本地运行备用）
├── requirements.txt             # Python 依赖
├── .gitignore                   # 忽略 .venv/、screenshots/ 等
├── spec/                        # 规约书
│   ├── pr.spec.md               # 产品需求规格书
│   ├── userstory.spec.md        # 用户故事规格书
│   └── sys.spec.md              # 系统架构规格书
├── formatter_core/              # SQL 格式化核心（Pyodide 前端加载）
├── static/                      # 前端静态资源
│   ├── app.js
│   ├── style.css
│   └── pyodide-loader.js
└── tests/                       # 后端接口测试（本地 Flask 模式用）
    └── test_app.py
```

## 环境要求

- 现代浏览器（支持 WebAssembly）
- 首次访问需联网加载 Pyodide 运行时
- 本地开发可选 Python 3.11+（用于 Flask 备用模式）

## 运行方式

### 方式一：Cloudflare Pages（推荐）

1. 仓库已推送至 GitHub。
2. 在 Cloudflare Pages 创建项目，绑定 GitHub 仓库 `wxmpro/sql-formatter-web`。
3. 构建设置：
   - **Build command**：（留空，无需构建）
   - **Build output directory**：`/`（项目根目录）
4. 保存并部署，然后绑定自定义域名 `jinkun.us.ci`。

### 方式二：本地静态服务器

```bash
cd /Users/xinmin/openmind/10_app_web_dev/projects/web/tools/sql-formatter-web
python -m http.server 8080
```

浏览器访问：`http://localhost:8080`

### 方式三：本地 Flask（备用）

```bash
cd /Users/xinmin/openmind/10_app_web_dev/projects/web/tools/sql-formatter-web
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
python app.py
```

浏览器访问：`http://127.0.0.1:5000`

## 运行测试

```bash
source .venv/bin/activate
python -m pytest tests/test_app.py -v
```

> 注意：测试仅覆盖 Flask 备用模式，Pyodide 前端模式通过浏览器验证。

## 技术栈

- **格式化核心**：Python 3 + 自定义 lexer/FSM（Pyodide 在浏览器内运行）
- **前端**：原生 HTML5 + CSS3 + JavaScript
- **托管**：Cloudflare Pages（静态站点）
- **测试**：pytest（Flask 备用模式）

## 相关文档

- 主 PRD：`/Users/xinmin/openmind/10_app_web_dev/prds/sql-formatter-web_2026-07-14_v1.0.0.md`
- 项目规约书：`spec/`

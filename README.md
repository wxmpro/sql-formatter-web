# SQL 格式化器 Web 界面

在浏览器中粘贴原始 SQL，即时获得规范化结果。

本项目是 `10_app_web_dev` workspace 下的第一个 Web 工具项目，为已有的 SQL 格式化核心（`formatter_core/`）提供一个零配置、本地运行的 Web 界面。

## 功能特性

- 左栏输入原始 SQL，右栏查看格式化结果
- 支持多条 SQL 语句按分号切分格式化
- 一键复制格式化结果到剪贴板
- 加载示例、清空输入
- 错误提示与容灾回退提示
- 本地离线运行，敏感 SQL 不离开本机
- 响应式布局：宽屏双栏、窄屏上下堆叠

## 目录结构

```text
sql-formatter-web/
├── README.md                    # 本文件
├── app.py                       # Flask 后端入口
├── requirements.txt             # Python 依赖
├── .gitignore                   # 忽略 .venv/ 等
├── spec/                        # 规约书
│   ├── pr.spec.md               # 产品需求规格书
│   ├── userstory.spec.md        # 用户故事规格书
│   └── sys.spec.md              # 系统架构规格书
├── formatter_core/              # SQL 格式化核心（只读副本）
├── static/                      # 前端静态资源
│   ├── index.html
│   ├── style.css
│   └── app.js
└── tests/                       # 后端接口测试
    └── test_app.py
```

## 环境要求

- Python 3.11+
- 推荐使用 [uv](https://github.com/astral-sh/uv) 管理依赖

## 启动方式

```bash
cd /Users/xinmin/openmind/10_app_web_dev/projects/web/tools/sql-formatter-web

# 创建虚拟环境（推荐 uv）
uv venv .venv
source .venv/bin/activate

# 安装依赖
uv pip install -r requirements.txt

# 启动服务
python app.py
```

浏览器访问：`http://127.0.0.1:5000`

### 局域网分享

```bash
python app.py --host=0.0.0.0 --port=5000
```

**注意**：此方式无认证，仅在受信任内网使用。

## 运行测试

```bash
source .venv/bin/activate
python -m pytest tests/test_app.py -v
```

## 技术栈

- **后端**：Python 3 + Flask
- **前端**：原生 HTML5 + CSS3 + JavaScript
- **通信**：RESTful JSON API (`POST /format`)
- **测试**：pytest

## 核心设计原则

- Web 层仅作为 `formatter_core.format_sql_file` 的 HTTP adapter，不实现任何格式化规则。
- `formatter_core/` 是从 `tools_v6` 复制的只读副本，与原仓库解耦。
- 所有界面文案使用中文。

## 相关文档

- 主 PRD：`/Users/xinmin/openmind/10_app_web_dev/prds/sql-formatter-web_2026-07-14_v1.0.0.md`
- 项目规约书：`spec/`

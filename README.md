# SQL 格式化器 Web 界面

在浏览器中粘贴原始 SQL，即时获得规范化结果。

本项目为 SQL 格式化核心（`formatter_core/`）提供一个零配置、本地运行的 Web 界面。

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

## 排版契约

格式化行为由 [`FORMAT_STYLE_SPEC.md`](./FORMAT_STYLE_SPEC.md) 定义，引擎实现以该文档为准。
核心要点：

| 主题 | 规则 |
|------|------|
| CASE WHEN | 三档判定：D1 单分支整块一行 / D2 多分支每分支一行（条件不展开）/ D3 条件复杂时展开并缩进 |
| 关键字小写 | 三层分层：语法关键字无条件小写；函数名仅在紧跟 `(` 时小写；类型名仅在类型位置小写；引号内与别名原样保留 |
| 孤儿行 | 禁止产生"只含单个关键字"的碎行 |
| 行宽预算 | 默认 100 字符 |

示例：

```sql
-- 单分支：整块一行
select
   case when a = 1 and b = 2 and c = 3 then 4 else 0 end as x

-- 多分支：每分支一行，条件不展开
select
   case
     when a.flg = 'A' then '是'
     when a.flg = 'B' then '否'
     else '未知'
   end as flg_desc
```

## 目录结构

```text
sql-formatter-web/
├── index.html                   # 前端入口（静态托管根页面）
├── README.md                    # 本文件
├── FORMAT_STYLE_SPEC.md         # 排版契约（风格规格，引擎行为的唯一依据）
├── app.py                       # Flask 后端入口（本地运行备用）
├── requirements.txt             # 运行时依赖
├── requirements-dev.txt         # 开发/测试依赖
├── .gitignore                   # 忽略本地文件与敏感配置
├── .github/workflows/ci.yml     # CI：pytest + 回归门禁
├── formatter_core/              # SQL 格式化核心（Pyodide 前端加载）
├── static/                      # 前端静态资源
│   ├── app.js
│   ├── style.css
│   └── pyodide-loader.js
├── tests/                       # 测试
│   ├── test_app.py              # Flask 接口测试
│   ├── test_golden_cases.py     # 黄金用例（排版契约门禁）
│   ├── test_verification.py     # 历史 Bug 回归
│   └── corpus/                  # 回归语料（16 个代表性 SQL）
└── tools/
    ├── regression_check.py      # 幂等性 / 语义等价 / 孤儿行 回归门禁
    └── batch_format.py          # 批量规范化（目录结构保持 + 三道门禁 + 报告）
```

## 批量规范化

```bash
python3 tools/batch_format.py \
  --src  <源目录> --dst <目标目录> \
  [--suffix _step1] [--alias "旧层名=新层名"] \
  [--dry-run] [--report report.json]
```

- **源目录只读**，绝不写入；输出保持相对目录结构
- 每个文件过三道门禁：幂等性 / 代码 token 序列等价 / 无孤儿行
- 源文件本身语法不完整时，按**原文切片**原样透传（安全降级），并在报告中单列
- `--dry-run` 只分析不写入；`--report` 输出 JSON 明细

> 幂等性契约与全量归因结论见 [`FORMAT_STYLE_SPEC.md`](./FORMAT_STYLE_SPEC.md) §八。

## 环境要求

- 现代浏览器（支持 WebAssembly）
- 首次访问需联网加载 Pyodide 运行时
- 本地开发可选 Python 3.11+（用于 Flask 备用模式）

## 运行方式

### 方式一：Cloudflare Pages（推荐）

- 主访问地址：`https://jinkun.us.ci/`
- 备用访问地址：`https://sql-formatter-web.pages.dev/`

1. 将本仓库推送至 GitHub，或在 Cloudflare Pages 通过直接上传部署。
2. 构建设置：
   - **Build command**：（留空，无需构建）
   - **Build output directory**：`/`（项目根目录）
3. 保存并部署。

### 方式二：本地静态服务器

```bash
cd <项目目录>
python -m http.server 8080
```

浏览器访问：`http://localhost:8080`

### 方式三：本地 Flask（备用）

```bash
cd <项目目录>
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
python app.py
```

浏览器访问：`http://127.0.0.1:5000`

## 部署（Wrangler 直接上传）

```bash
cd <项目目录>
wrangler pages deploy dist --project-name=sql-formatter-web --branch=main
```

部署凭证已写入 `.env`，该文件已被 Git 忽略。

## 运行测试

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt

# 黄金用例 + 接口测试 + 历史 Bug 回归
python -m pytest tests/ -v

# 幂等性 / 语义等价 / 孤儿行 回归门禁（对 tests/corpus/ 全量语料）
python tools/regression_check.py
```

> 回归门禁的三道判定（见 `FORMAT_STYLE_SPEC.md` §七、§八）：
> 1. 幂等：`format(format(x)) == format(x)`
> 2. 语义等价：格式化前后**代码 token 序列**不变（仅大小写规范化）
> 3. 无孤儿行：不产生只含单个关键字的碎行

> 回归门禁的三道判定（见 `FORMAT_STYLE_SPEC.md` §七）：
> 1. 幂等：`format(format(x)) == format(x)`
> 2. 语义等价：格式化前后标识符/字符串集合不变（仅大小写规范化）
> 3. 无孤儿行：不产生只含单个关键字的碎行

## 技术栈

- **格式化核心**：Python 3 + 自定义 lexer/FSM（Pyodide 在浏览器内运行）
- **前端**：原生 HTML5 + CSS3 + JavaScript
- **托管**：Cloudflare Pages（静态站点）
- **测试**：pytest（Flask 备用模式）

"""SQL 格式化器 Web 后端（本地 Flask 备用模式）。"""

import argparse
import os

from flask import Flask, jsonify, request

from formatter_core import format_sql_file, format_sql_file_html

app = Flask(__name__)


@app.route("/")
def index():
    """返回前端页面。"""
    index_path = os.path.join(app.root_path, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()


@app.route("/format", methods=["POST"])
def format_sql():
    """接收原始 SQL，返回格式化后的 SQL。"""
    data = request.get_json(silent=True) or {}
    sql = data.get("sql", "")

    if not isinstance(sql, str) or not sql.strip():
        return (
            jsonify(
                {"success": False, "error": "格式化失败：输入 SQL 为空", "formatted": None}
            ),
            400,
        )

    try:
        formatted = format_sql_file(sql)
        formatted_html = format_sql_file_html(sql)
    except Exception as exc:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"格式化失败：{exc}",
                    "formatted": None,
                    "formatted_html": None,
                }
            ),
            500,
        )

    return jsonify(
        {"success": True, "formatted": formatted, "formatted_html": formatted_html}
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SQL 格式化器 Web 服务")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", type=int, default=5000, help="监听端口")
    args = parser.parse_args()

    app.run(host=args.host, port=args.port, debug=False)

"""SQL 格式化器 Web 后端测试。"""

import pytest

from app import app


@pytest.fixture
def client():
    """提供 Flask 测试客户端。"""
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_index_returns_html(client):
    """GET / 应返回前端页面。"""
    response = client.get("/")
    assert response.status_code == 200
    assert b"SQL \xe6\xa0\xbc\xe5\xbc\x8f\xe5\x8c\x96\xe5\x99\xa8" in response.data


def test_format_normal_sql(client):
    """POST /format 应返回格式化后的 SQL 及高亮 HTML。"""
    response = client.post("/format", json={"sql": "select id from user where id=1"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "select" in data["formatted"].lower()
    assert "from" in data["formatted"].lower()
    assert "formatted_html" in data
    assert 'class="sql-keyword"' in data["formatted_html"].lower()
    assert 'class="sql-number"' in data["formatted_html"].lower()


def test_format_empty_sql(client):
    """空 SQL 应返回 400 错误。"""
    response = client.post("/format", json={"sql": ""})
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "空" in data["error"]


def test_format_whitespace_only_sql(client):
    """仅包含空白字符的 SQL 应视为空输入。"""
    response = client.post("/format", json={"sql": "   \n\t  "})
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False


def test_format_missing_sql_field(client):
    """请求体缺少 sql 字段时应视为空输入。"""
    response = client.post("/format", json={})
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False


def test_format_invalid_content_type(client):
    """非 JSON 请求应被优雅处理。"""
    response = client.post("/format", data="not json")
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False

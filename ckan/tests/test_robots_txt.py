

def test_robots_txt(app):
    res = app.get("/robots.txt")
    assert res.status_code == 200
    assert res.headers.get("Content-Type") == "text/plain; charset=utf-8"
    assert "User-agent" in res.body

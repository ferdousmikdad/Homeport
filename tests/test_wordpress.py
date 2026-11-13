"""WordPress mode and live-URL proxying."""

from __future__ import annotations

import gzip
import os
import shutil
import subprocess

import pytest

from backend import proxy, shellenv, wordpress


def make_wp(root, with_config=False):
    (root / "wp-includes").mkdir(parents=True)
    (root / "wp-includes" / "version.php").write_text("<?php $wp_version = '6.8';")
    (root / "wp-load.php").write_text("<?php")
    (root / "wp-config-sample.php").write_text(
        "<?php\n"
        "define( 'DB_NAME', 'database_name_here' );\n"
        "define( 'DB_USER', 'username_here' );\n"
        "define( 'DB_PASSWORD', 'password_here' );\n"
        "define( 'DB_HOST', 'localhost' );\n"
        "define( 'AUTH_KEY', 'put your unique phrase here' );\n"
        "define( 'SECURE_AUTH_KEY', 'put your unique phrase here' );\n"
        "$table_prefix = 'wp_';\n"
    )
    if with_config:
        (root / "wp-config.php").write_text(
            "<?php\ndefine('DB_NAME', 'live_db');\ndefine(\"DB_USER\", \"live_user\");\n"
            "define('DB_PASSWORD', 'se\\'cret');\ndefine('DB_HOST', 'db.example.com');\n$table_prefix = 'xy_';\n"
        )
    return str(root)


def test_detection_and_status(tmp_path):
    assert not wordpress.is_wordpress(str(tmp_path))
    path = make_wp(tmp_path)
    assert wordpress.is_wordpress(path)
    st = wordpress.status(path)
    assert st["needs_setup"] and not st["configured"] and not st["helper"]


def test_fresh_config_from_sample(tmp_path):
    path = make_wp(tmp_path)
    wordpress.write_config(path, "wp_demo", "root", "", "127.0.0.1:3307")
    text = (tmp_path / "wp-config.php").read_text()
    assert "put your unique phrase here" not in text
    assert wordpress.read_config(path) == {"DB_NAME": "wp_demo", "DB_USER": "root", "DB_PASSWORD": "",
                                           "DB_HOST": "127.0.0.1:3307", "table_prefix": "wp_"}
    assert not (tmp_path / wordpress.BACKUP_NAME).exists()  # nothing to back up


def test_existing_config_is_backed_up_once(tmp_path):
    path = make_wp(tmp_path, with_config=True)
    original = (tmp_path / "wp-config.php").read_text()
    assert wordpress.read_config(path)["DB_HOST"] == "db.example.com"
    wordpress.write_config(path, "wp_one", "root", "", "127.0.0.1:3307")
    wordpress.write_config(path, "wp_two", "root", "", "127.0.0.1:3308")
    assert (tmp_path / wordpress.BACKUP_NAME).read_text() == original
    conf = wordpress.read_config(path)
    assert conf["DB_NAME"] == "wp_two" and conf["DB_HOST"] == "127.0.0.1:3308" and conf["table_prefix"] == "xy_"


def test_bad_database_name_rejected(tmp_path):
    path = make_wp(tmp_path)
    with pytest.raises(ValueError):
        wordpress.write_config(path, "x; DROP DATABASE y", "root", "", "h")
    with pytest.raises(ValueError):
        wordpress.create_database(3306, "bad-name!")


def test_helper_install_and_status(tmp_path):
    path = make_wp(tmp_path)
    wordpress.write_config(path, "wp_demo", "root", "", "127.0.0.1:3307")
    wordpress.install_helper(path)
    st = wordpress.status(path, "127.0.0.1:3307")
    assert st["linked"] and st["helper"] and not st["needs_setup"]
    assert wordpress.status(path, "127.0.0.1:9999")["needs_setup"]  # pointed elsewhere


@pytest.mark.skipif(not shellenv.which("php"), reason="php not installed")
def test_helper_maps_stored_address_to_current(tmp_path):
    (tmp_path / "homeport-url.php").write_text(wordpress.HELPER_PHP)
    (tmp_path / "harness.php").write_text(r"""<?php
define('ABSPATH', __DIR__ . '/');
$F = []; $A = [];
function add_filter($n, $cb, $p = 10) { global $F; $F[$n] = $cb; }
function add_action($n, $cb, $p = 10) { global $A; $A[$n] = $cb; }
class Db { public $options = 'wp_options'; function get_var($q) { return 'https://theirsite.com/blog'; } }
$wpdb = new Db();
$_SERVER['HTTP_HOST'] = 'localhost:8000';
$_SERVER['HTTP_X_FORWARDED_HOST'] = 'abc.trycloudflare.com';
$_SERVER['HTTP_X_FORWARDED_PROTO'] = 'https';
require __DIR__ . '/homeport-url.php';
echo $F['option_home']('https://theirsite.com/blog'), "\n";
$A['muplugins_loaded']();
echo '<img src="https://theirsite.com/a.jpg"> https://theirsite.com.evil.net';
ob_end_flush();
""")
    out = subprocess.run(["php", str(tmp_path / "harness.php")], capture_output=True, text=True,
                         env={**os.environ, "PATH": shellenv.user_path()}).stdout.splitlines()
    assert out[0] == "https://abc.trycloudflare.com/blog"
    assert out[1] == '<img src="https://abc.trycloudflare.com/a.jpg"> https://theirsite.com.evil.net'


def test_import_unzips_and_uses_mysql_client(tmp_path, monkeypatch):
    dump = tmp_path / "site.sql.gz"
    with gzip.open(dump, "wb") as fh:
        fh.write(b"CREATE TABLE t (x int);\nINSERT INTO t VALUES (1);\n")
    seen = {}

    def fake_run(args, stdin=None, **kw):
        seen["args"] = args
        seen["sql"] = stdin.read()
        return subprocess.CompletedProcess(args, 0, b"", b"")

    monkeypatch.setattr(wordpress.shellenv, "which", lambda t: "/usr/bin/mysql" if t == "mysql" else None)
    monkeypatch.setattr(wordpress.subprocess, "run", fake_run)
    assert wordpress.import_sql(str(dump), 3307, "wp_demo") == "imported with mysql"
    assert seen["args"][-1] == "wp_demo" and "-P" in seen["args"] and "3307" in seen["args"]
    assert seen["sql"].startswith(b"CREATE TABLE")


def test_wordpress_routes(client, isolated_registry, tmp_path, monkeypatch):
    from backend import services

    site = tmp_path / "blog"
    path = make_wp(site)
    isolated_registry.add({"name": "Blog", "path": path, "command": "php -S 127.0.0.1:8001 -t ."})
    state = client.get("/api/apps").json()[0]
    assert state["wordpress"]["needs_setup"] is True
    assert client.post("/api/apps/blog/wordpress/import", content=b"x").status_code == 409
    monkeypatch.setattr(services.shellenv, "which", lambda t: None)  # no MySQL, no Docker
    resp = client.post("/api/apps/blog/wordpress/setup")
    assert resp.status_code == 409 and "MySQL" in resp.json()["detail"]
    assert [a["name"] for a in client.get("/api/apps").json()] == ["Blog"]  # nothing half-created
    plain = tmp_path / "plain"
    plain.mkdir()
    isolated_registry.add({"name": "Plain", "path": str(plain), "command": "x"})
    assert client.get("/api/apps/plain/wordpress").status_code == 404


# --- live URLs through the proxy -------------------------------------------------
def test_localhost_links_rewritten_on_port_boundary():
    swaps = proxy._localhost_swaps(8000, "https://abc.trycloudflare.com")
    src = (b'<a href="http://localhost:8000/x"><img src="//127.0.0.1:8000/i.png">'
           b'{"u":"http:\\/\\/localhost:8000\\/api"} http://localhost:80001/keep')
    out = proxy._apply(src, swaps)
    assert b'href="https://abc.trycloudflare.com/x"' in out
    assert b'src="//abc.trycloudflare.com/i.png"' in out
    assert b'https:\\/\\/abc.trycloudflare.com\\/api' in out
    assert b"http://localhost:80001/keep" in out


@pytest.mark.skipif(not shutil.which("php") and not shellenv.which("php"), reason="php not installed")
def test_named_url_sends_forwarded_headers_and_rewrites(client, isolated_registry, tmp_path):
    import socket

    from _helpers import wait_until

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    (tmp_path / "index.php").write_text(
        "<?php if ($_SERVER['REQUEST_URI'] === '/go') { header('Location: http://localhost:" + str(port) + "/in'); exit; }\n"
        "echo '<a href=\"http://localhost:" + str(port) + "/x\">', $_SERVER['HTTP_X_FORWARDED_HOST'];"
    )
    isolated_registry.add({"name": "Php", "path": str(tmp_path), "command": f"php -S 127.0.0.1:{port} -t .", "port": port})
    client.post("/api/apps/php/start")
    assert wait_until(lambda: client.get("/api/apps/php").json()["status"] == "running", timeout=15)
    host = {"Host": "php.localhost:7777"}
    resp = client.get("/", headers=host)
    assert resp.text == '<a href="http://php.localhost:7777/x">php.localhost:7777'
    redirect = client.get("/go", headers=host, follow_redirects=False)
    assert redirect.headers["location"] == "http://php.localhost:7777/in"
    client.post("/api/apps/php/stop")

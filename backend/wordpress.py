"""backend/wordpress.py — WordPress mode: database, wp-config, live URLs, import.

Turns a WordPress folder (fresh download or a copy of a live site) into a site
that works on localhost, <id>.localhost, phones and public share links:

1. a MySQL/MariaDB database (Homeport service) and ``wp-config.php`` pointing
   at it — the original config is backed up once;
2. a must-use plugin (``wp-content/mu-plugins/homeport-url.php``) that serves
   the site on whatever address it is opened with and maps the site's stored
   address (e.g. https://theirsite.com) to it — nothing in the database is
   rewritten, delete the file to go back;
3. importing a ``.sql`` / ``.sql.gz`` backup.

Database work runs through PHP (needed for WordPress anyway) unless a MySQL
client or the service's Docker container is available.
"""

from __future__ import annotations

import gzip
import os
import re
import secrets
import shutil
import subprocess
import tempfile
from typing import Optional

from . import osutil, shellenv

__all__ = ["is_wordpress", "status", "read_config", "write_config", "install_helper",
           "create_database", "import_sql", "HELPER_REL"]

HELPER_REL = os.path.join("wp-content", "mu-plugins", "homeport-url.php")
BACKUP_NAME = "wp-config.homeport-backup.php"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_DB_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,64}$")
_DEFINE_RE = r"""define\(\s*['"]{key}['"]\s*,\s*(['"])(.*?)\1\s*\)"""


def is_wordpress(path: str) -> bool:
    if not path or not os.path.isdir(path):
        return False
    j = lambda *p: os.path.join(path, *p)  # noqa: E731
    has_core = os.path.isfile(j("wp-load.php")) or os.path.isfile(j("wp-includes", "version.php"))
    has_config = os.path.isfile(j("wp-config.php")) or os.path.isfile(j("wp-config-sample.php"))
    return has_core and has_config


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def read_config(path: str) -> dict:
    """DB settings from wp-config.php (empty dict when there is none)."""
    text = _read(os.path.join(path, "wp-config.php"))
    if not text:
        return {}
    out = {}
    for key in ("DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST"):
        m = re.search(_DEFINE_RE.format(key=key), text)
        if m:
            out[key] = m.group(2)
    m = re.search(r"""\$table_prefix\s*=\s*(['"])(.*?)\1""", text)
    if m:
        out["table_prefix"] = m.group(2)
    return out


def status(path: str, expected_host: Optional[str] = None) -> Optional[dict]:
    """Small summary for the dashboard, or None when it isn't WordPress."""
    if not is_wordpress(path):
        return None
    conf = read_config(path)
    configured = bool(conf.get("DB_NAME")) and conf.get("DB_NAME") != "database_name_here"
    linked = configured and (expected_host is None or conf.get("DB_HOST") == expected_host)
    helper = os.path.isfile(os.path.join(path, HELPER_REL))
    return {
        "configured": configured,
        "linked": linked,
        "helper": helper,
        "db_name": conf.get("DB_NAME") if configured else None,
        "db_host": conf.get("DB_HOST"),
        "backup": os.path.isfile(os.path.join(path, BACKUP_NAME)),
        "needs_setup": not (linked and helper),
    }


def _php_str(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def write_config(path: str, db_name: str, user: str, password: str, host: str) -> str:
    """Point wp-config.php at the database (creating it from the sample when
    missing). The original is copied to wp-config.homeport-backup.php once."""
    if not _DB_NAME_RE.match(db_name):
        raise ValueError("invalid database name")
    cfg_path = os.path.join(path, "wp-config.php")
    if os.path.isfile(cfg_path):
        backup = os.path.join(path, BACKUP_NAME)
        if not os.path.exists(backup):
            shutil.copyfile(cfg_path, backup)
        text = _read(cfg_path)
    else:
        sample = os.path.join(path, "wp-config-sample.php")
        if not os.path.isfile(sample):
            raise ValueError("no wp-config.php or wp-config-sample.php in this folder")
        text = _read(sample)
        # fresh install: unique keys & salts instead of the sample placeholders
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_[]{}<>~+=,.;:/?|"
        text = re.sub(r"'put your unique phrase here'",
                      lambda _m: _php_str("".join(secrets.choice(alphabet) for _ in range(64))), text)

    values = {"DB_NAME": db_name, "DB_USER": user, "DB_PASSWORD": password, "DB_HOST": host}
    for key, value in values.items():
        pattern = re.compile(_DEFINE_RE.format(key=key))
        replacement = f"define( '{key}', {_php_str(value)} )"
        if pattern.search(text):
            text = pattern.sub(lambda _m, r=replacement: r, text, count=1)
        else:
            text = text.replace("<?php", "<?php\n" + replacement + ";", 1)
    with open(cfg_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return cfg_path


HELPER_PHP = r"""<?php
/**
 * Plugin Name: Homeport live URL
 * Description: Added by Homeport. Serves this site on whatever address it is opened with
 *              (localhost, name.localhost, Wi-Fi, share links) and maps the site's stored
 *              address to it. Nothing in the database is changed — delete this file to undo.
 */
if (!defined('ABSPATH')) { exit; }
if (defined('WP_CLI') && WP_CLI) { return; }

function homeport_current_origin() {
    static $origin = null;
    if ($origin !== null) { return $origin; }
    $host = '';
    if (!empty($_SERVER['HTTP_X_FORWARDED_HOST'])) {
        $host = trim(explode(',', $_SERVER['HTTP_X_FORWARDED_HOST'])[0]);
    } elseif (!empty($_SERVER['HTTP_HOST'])) {
        $host = $_SERVER['HTTP_HOST'];
    }
    if ($host === '' || !preg_match('/^[A-Za-z0-9.\-:\[\]]+$/', $host)) { return $origin = ''; }
    $https = false;
    if (!empty($_SERVER['HTTP_X_FORWARDED_PROTO'])) {
        $https = strtolower(trim(explode(',', $_SERVER['HTTP_X_FORWARDED_PROTO'])[0])) === 'https';
    } elseif (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') {
        $https = true;
    }
    if ($https) { $_SERVER['HTTPS'] = 'on'; }
    return $origin = ($https ? 'https' : 'http') . '://' . $host;
}

function homeport_stored_origin() {
    static $stored = null;
    if ($stored !== null) { return $stored; }
    global $wpdb;
    $raw = $wpdb ? $wpdb->get_var("SELECT option_value FROM {$wpdb->options} WHERE option_name = 'home' LIMIT 1") : '';
    return $stored = $raw ? preg_replace('#^(https?://[^/]+).*$#i', '$1', $raw) : '';
}

function homeport_swap_url($url) {
    $now = homeport_current_origin();
    return ($now === '' || !is_string($url)) ? $url : preg_replace('#^https?://[^/]+#i', $now, $url);
}
add_filter('option_home', 'homeport_swap_url', 99);
add_filter('option_siteurl', 'homeport_swap_url', 99);

// Links saved with the stored address (images, menus…) point at the current one.
add_action('muplugins_loaded', function () {
    $old = homeport_stored_origin();
    $now = homeport_current_origin();
    if ($old === '' || $now === '' || strcasecmp($old, $now) === 0) { return; }
    $old_host = preg_quote(preg_replace('#^https?://#i', '', $old), '#');
    $now_host = preg_replace('#^https?://#i', '', $now);
    ob_start(function ($html) use ($old_host, $now, $now_host) {
        $html = preg_replace('#https?://' . $old_host . '(?![A-Za-z0-9.\-])#i', $now, $html);
        $html = preg_replace('#https?:\\\\/\\\\/' . $old_host . '(?![A-Za-z0-9.\-])#i', str_replace('/', '\/', $now), $html);
        return preg_replace('#(?<![A-Za-z:])//' . $old_host . '(?![A-Za-z0-9.\-])#i', '//' . $now_host, $html);
    });
});
"""


def install_helper(path: str) -> str:
    target = os.path.join(path, HELPER_REL)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(HELPER_PHP)
    return target


# ---------------------------------------------------------------------------
# database
# ---------------------------------------------------------------------------
_PHP_CREATE = r"""
mysqli_report(MYSQLI_REPORT_OFF);
$c = @mysqli_connect(getenv('HP_HOST'), getenv('HP_USER'), getenv('HP_PASS'), '', (int) getenv('HP_PORT'));
if (!$c) { fwrite(STDERR, 'connect: ' . mysqli_connect_error()); exit(2); }
$db = getenv('HP_DB');
if (!preg_match('/^[A-Za-z0-9_]{1,64}$/', $db)) { fwrite(STDERR, 'bad name'); exit(3); }
if (!mysqli_query($c, "CREATE DATABASE IF NOT EXISTS `$db` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")) {
    fwrite(STDERR, mysqli_error($c)); exit(4);
}
echo 'ok';
"""

_PHP_IMPORT = r"""
mysqli_report(MYSQLI_REPORT_OFF);
$c = @mysqli_connect(getenv('HP_HOST'), getenv('HP_USER'), getenv('HP_PASS'), getenv('HP_DB'), (int) getenv('HP_PORT'));
if (!$c) { fwrite(STDERR, 'connect: ' . mysqli_connect_error()); exit(2); }
mysqli_set_charset($c, 'utf8mb4');
$fh = fopen(getenv('HP_FILE'), 'r');
$stmt = ''; $n = 0;
while (($line = fgets($fh)) !== false) {
    $t = ltrim($line);
    if ($stmt === '' && ($t === '' || strpos($t, '--') === 0 || strpos($t, '#') === 0)) { continue; }
    $stmt .= $line;
    if (preg_match('/;\s*$/', $line)) {
        if (!mysqli_query($c, $stmt)) { fwrite(STDERR, mysqli_error($c) . "\n" . substr($stmt, 0, 200)); exit(5); }
        $stmt = ''; $n++;
    }
}
if (trim($stmt) !== '' && !mysqli_query($c, $stmt)) { fwrite(STDERR, mysqli_error($c)); exit(5); }
echo $n;
"""


def _php() -> str:
    php = shellenv.which("php")
    if not php:
        raise RuntimeError("PHP isn't installed — WordPress needs it (e.g. Laravel Herd, or php.net)")
    return php


def _run(cmd: list, env: dict, timeout: float = 600, stdin=None) -> subprocess.CompletedProcess:
    full_env = {**os.environ, "PATH": shellenv.user_path(), **env}
    return subprocess.run(cmd, env=full_env, stdin=stdin, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout,
                          creationflags=_NO_WINDOW if osutil.IS_WINDOWS else 0)


def php_has_mysqli() -> bool:
    try:
        res = _run([_php(), "-r", "echo extension_loaded('mysqli') ? 'yes' : 'no';"], {}, timeout=30)
    except (RuntimeError, OSError, subprocess.SubprocessError):
        return False
    return res.stdout.strip() == "yes"


def create_database(port: int, db_name: str, user: str = "root", password: str = "") -> None:
    if not _DB_NAME_RE.match(db_name):
        raise ValueError("invalid database name")
    if not php_has_mysqli():
        raise RuntimeError("PHP's mysqli extension isn't enabled — WordPress needs it to talk to MySQL")
    env = {"HP_HOST": "127.0.0.1", "HP_PORT": str(port), "HP_USER": user, "HP_PASS": password, "HP_DB": db_name}
    res = _run([_php(), "-r", _PHP_CREATE], env, timeout=60)
    if res.returncode != 0:
        raise RuntimeError("couldn't create the database: " + (res.stderr or res.stdout).strip()[-300:])


def import_sql(sql_file: str, port: int, db_name: str, *, user: str = "root", password: str = "",
               docker_container: Optional[str] = None) -> str:
    """Load a .sql (or .sql.gz) dump into the database. Returns a short summary."""
    if not _DB_NAME_RE.match(db_name):
        raise ValueError("invalid database name")
    plain = sql_file
    tmp_dir = None
    try:
        with open(sql_file, "rb") as fh:
            gz = fh.read(2) == b"\x1f\x8b"
        if gz:
            tmp_dir = tempfile.mkdtemp(prefix="homeport-sql-")
            plain = os.path.join(tmp_dir, "dump.sql")
            with gzip.open(sql_file, "rb") as src, open(plain, "wb") as dst:
                shutil.copyfileobj(src, dst)

        client = shellenv.which("mariadb") or shellenv.which("mysql")
        if docker_container and shellenv.which("docker"):
            with open(plain, "rb") as fh:
                res = subprocess.run(["docker", "exec", "-i", docker_container, "mysql", "-u" + user, db_name],
                                     stdin=fh, capture_output=True, timeout=3600,
                                     env={**os.environ, "PATH": shellenv.user_path()})
            ok, err = res.returncode == 0, res.stderr.decode("utf-8", "replace")
            how = "docker"
        elif client:
            args = [client, "-h", "127.0.0.1", "-P", str(port), "-u", user, db_name]
            env = {"MYSQL_PWD": password} if password else {}
            with open(plain, "rb") as fh:
                res = subprocess.run(args, stdin=fh, capture_output=True, timeout=3600,
                                     env={**os.environ, "PATH": shellenv.user_path(), **env})
            ok, err = res.returncode == 0, res.stderr.decode("utf-8", "replace")
            how = os.path.basename(client)
        else:
            if not php_has_mysqli():
                raise RuntimeError("PHP's mysqli extension isn't enabled — needed to import the database")
            env = {"HP_HOST": "127.0.0.1", "HP_PORT": str(port), "HP_USER": user, "HP_PASS": password,
                   "HP_DB": db_name, "HP_FILE": plain}
            res = _run([_php(), "-r", _PHP_IMPORT], env, timeout=3600)
            ok, err = res.returncode == 0, res.stderr
            how = "php"
        if not ok:
            raise RuntimeError("import failed: " + err.strip()[-400:])
        return f"imported with {how}"
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)

"""
Reklama5 Огласи – локална Flask апликација.

Пуштање:
    pip install -r requirements.txt
    python app.py
Потоа отвори http://127.0.0.1:5000
"""

import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

import requests
from flask import (Flask, flash, g, redirect, render_template, request,
                   url_for)

import scraper

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "reklama5.db"

app = Flask(__name__)
app.secret_key = "reklama5-local-app"

check_lock = threading.Lock()
status = {"running": False, "last_run": None, "last_error": None}


# ======================================================================= база

SCHEMA = """
CREATE TABLE IF NOT EXISTS searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category_id INTEGER NOT NULL DEFAULT 159,
    city_id INTEGER,
    only_sale INTEGER NOT NULL DEFAULT 1,
    price_min INTEGER, price_max INTEGER,
    m2_min REAL, m2_max REAL,
    rooms_min REAL, rooms_max REAL,
    include_words TEXT DEFAULT '',
    exclude_words TEXT DEFAULT '',
    skip_promoted INTEGER NOT NULL DEFAULT 0,
    max_pages INTEGER NOT NULL DEFAULT 5,
    notify INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1,
    synced INTEGER NOT NULL DEFAULT 0,
    last_checked TEXT
);
CREATE TABLE IF NOT EXISTS ads (
    id TEXT NOT NULL,
    search_id INTEGER NOT NULL,
    title TEXT, url TEXT,
    price INTEGER, currency TEXT, price_text TEXT,
    m2 REAL, rooms REAL,
    description TEXT, city TEXT, image TEXT, posted TEXT,
    promoted INTEGER,
    first_seen TEXT,
    is_new INTEGER NOT NULL DEFAULT 1,
    favorite INTEGER NOT NULL DEFAULT 0,
    hidden INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (id, search_id)
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""

DEFAULT_SETTINGS = {
    "interval_min": "20",
    "telegram_token": "",
    "telegram_chat_id": "",
    "ntfy_topic": "",
}


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_db():
    if "db" not in g:
        g.db = connect()
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)
        for k, v in DEFAULT_SETTINGS.items():
            conn.execute("INSERT OR IGNORE INTO settings VALUES (?, ?)", (k, v))
        if conn.execute("SELECT COUNT(*) FROM searches").fetchone()[0] == 0:
            conn.execute(
                "INSERT INTO searches (name, category_id, city_id, price_min, price_max,"
                " exclude_words) VALUES (?,?,?,?,?,?)",
                ("Станови Битола", 159, 2, 25000, 60000,
                 "изнајмува, издава, iznajmuva, izdava"),
            )


def get_settings(conn):
    return {r["key"]: r["value"] for r in conn.execute("SELECT * FROM settings")}


# ======================================================================= нотификации

def send_notification(settings, message):
    """Праќа на Telegram и/или ntfy. Враќа листа грешки (празна = ок)."""
    errors = []
    token, chat = settings.get("telegram_token"), settings.get("telegram_chat_id")
    if token and chat:
        try:
            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                              data={"chat_id": chat, "text": message}, timeout=20)
            if not r.ok:
                errors.append(f"Telegram: {r.status_code} {r.text[:120]}")
        except requests.RequestException as e:
            errors.append(f"Telegram: {e}")
    topic = settings.get("ntfy_topic")
    if topic:
        try:
            r = requests.post(f"https://ntfy.sh/{topic}", data=message.encode(),
                              headers={"Title": "Reklama5 - нов оглас"}, timeout=20)
            if not r.ok:
                errors.append(f"ntfy: {r.status_code}")
        except requests.RequestException as e:
            errors.append(f"ntfy: {e}")
    if not (token and chat) and not topic:
        errors.append("Немаш поставено Telegram или ntfy во Поставки.")
    return errors


def format_message(ad, search_name):
    lines = [f"🏠 Нов оглас – {search_name}", ad["title"], f"💶 {ad['price_text']}"]
    extra = []
    if ad["m2"]:
        extra.append(f"{ad['m2']:g} m²")
    if ad["rooms"]:
        extra.append(f"{ad['rooms']:g} соби")
    if extra:
        lines.append(" • ".join(extra))
    lines.append(ad["url"])
    return "\n".join(lines)


# ======================================================================= проверка

def check_search(conn, search, settings):
    """Проверува едно пребарување. Враќа број нови огласи."""
    ads = [a for a in scraper.fetch_all(search) if scraper.matches(a, search)]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    first_sync = not search["synced"]
    new_count = 0

    for ad in ads:
        exists = conn.execute("SELECT 1 FROM ads WHERE id=? AND search_id=?",
                              (ad["id"], search["id"])).fetchone()
        if exists:
            # освежи цена/наслов ако се сменети
            conn.execute(
                "UPDATE ads SET title=?, price=?, currency=?, price_text=?, image=?, posted=?"
                " WHERE id=? AND search_id=?",
                (ad["title"], ad["price"], ad["currency"], ad["price_text"],
                 ad["image"], ad["posted"], ad["id"], search["id"]))
            continue

        conn.execute(
            "INSERT INTO ads (id, search_id, title, url, price, currency, price_text, m2,"
            " rooms, description, city, image, posted, promoted, first_seen, is_new)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ad["id"], search["id"], ad["title"], ad["url"], ad["price"], ad["currency"],
             ad["price_text"], ad["m2"], ad["rooms"], ad["description"], ad["city"],
             ad["image"], ad["posted"], int(ad["promoted"]), now, 0 if first_sync else 1))
        if not first_sync:
            new_count += 1
            if search["notify"]:
                send_notification(settings, format_message(ad, search["name"]))

    conn.execute("UPDATE searches SET synced=1, last_checked=? WHERE id=?",
                 (now, search["id"]))
    conn.commit()
    return new_count


def run_check(search_id=None):
    """Ги проверува сите активни пребарувања (или само едно)."""
    if not check_lock.acquire(blocking=False):
        return None  # веќе тече проверка
    status["running"] = True
    total, errors = 0, []
    try:
        conn = connect()
        settings = get_settings(conn)
        q = "SELECT * FROM searches WHERE active=1"
        args = ()
        if search_id:
            q, args = "SELECT * FROM searches WHERE id=?", (search_id,)
        for s in conn.execute(q, args).fetchall():
            try:
                total += check_search(conn, s, settings)
            except Exception as e:  # noqa: BLE001
                errors.append(f"{s['name']}: {e}")
        conn.close()
    finally:
        status.update(running=False,
                      last_run=datetime.now().strftime("%H:%M:%S"),
                      last_error="; ".join(errors) or None)
        check_lock.release()
    return total


def scheduler():
    """Позадинска нишка – проверува на секои N минути."""
    time.sleep(3)
    while True:
        run_check()
        conn = connect()
        minutes = int(get_settings(conn).get("interval_min") or 20)
        conn.close()
        time.sleep(max(minutes, 5) * 60)


# ======================================================================= страници

@app.context_processor
def inject_globals():
    db = get_db()
    new_total = db.execute(
        "SELECT COUNT(*) FROM ads WHERE is_new=1 AND hidden=0").fetchone()[0]
    return {"status": status, "new_total": new_total,
            "CITIES": scraper.CITIES, "CATEGORIES": scraper.CATEGORIES}


@app.route("/")
def index():
    db = get_db()
    searches = db.execute("SELECT * FROM searches ORDER BY id").fetchall()
    search_id = request.args.get("search", type=int)
    view = request.args.get("view", "all")       # all | new | fav | hidden
    sort = request.args.get("sort", "newest")    # newest | price_asc | price_desc | m2

    where, args = ["1=1"], []
    if search_id:
        where.append("a.search_id=?")
        args.append(search_id)
    if view == "new":
        where.append("a.is_new=1 AND a.hidden=0")
    elif view == "fav":
        where.append("a.favorite=1")
    elif view == "hidden":
        where.append("a.hidden=1")
    else:
        where.append("a.hidden=0")

    order = {
        "newest": "a.first_seen DESC, CAST(a.id AS INTEGER) DESC",
        "price_asc": "a.price IS NULL, a.price ASC",
        "price_desc": "a.price DESC",
        "m2": "a.m2 IS NULL, a.m2 DESC",
    }.get(sort, "a.first_seen DESC")

    ads = db.execute(
        f"SELECT a.*, s.name AS search_name FROM ads a JOIN searches s ON s.id=a.search_id"
        f" WHERE {' AND '.join(where)}"
        f"{'' if search_id else ' GROUP BY a.id'}"   # без дупликати во „Сите“
        f" ORDER BY {order}", args).fetchall()

    counts = {r["search_id"]: r["c"] for r in db.execute(
        "SELECT search_id, COUNT(*) c FROM ads WHERE hidden=0 GROUP BY search_id")}
    return render_template("index.html", ads=ads, searches=searches, counts=counts,
                           search_id=search_id, view=view, sort=sort)


@app.route("/open/<int:search_id>/<ad_id>")
def open_ad(search_id, ad_id):
    """Го означува огласот како видено и те носи на reklama5."""
    db = get_db()
    db.execute("UPDATE ads SET is_new=0 WHERE id=? AND search_id=?", (ad_id, search_id))
    db.commit()
    return redirect(f"{scraper.BASE_URL}/AdDetails?ad={ad_id}")


@app.post("/ad/<int:search_id>/<ad_id>/<action>")
def ad_action(search_id, ad_id, action):
    sql = {
        "favorite": "UPDATE ads SET favorite=1-favorite WHERE id=? AND search_id=?",
        "hide": "UPDATE ads SET hidden=1-hidden, is_new=0 WHERE id=? AND search_id=?",
        "seen": "UPDATE ads SET is_new=0 WHERE id=? AND search_id=?",
    }.get(action)
    if sql:
        db = get_db()
        db.execute(sql, (ad_id, search_id))
        db.commit()
    return redirect(request.referrer or url_for("index"))


@app.post("/mark-all-seen")
def mark_all_seen():
    db = get_db()
    db.execute("UPDATE ads SET is_new=0")
    db.commit()
    return redirect(request.referrer or url_for("index"))


@app.post("/check")
def check_now():
    search_id = request.form.get("search_id", type=int)
    result = run_check(search_id)
    if result is None:
        flash("Проверката веќе тече, пробај за малку.", "info")
    elif status["last_error"]:
        flash(f"Грешка: {status['last_error']}", "error")
    else:
        flash(f"Проверката заврши. Нови огласи: {result}", "ok")
    return redirect(request.referrer or url_for("index"))


# ---------------------------------------------------------------- пребарувања

def _num(name, cast=int):
    v = request.form.get(name, "").strip().replace(".", "").replace(" ", "")
    if not v:
        return None
    try:
        return cast(v.replace(",", "."))
    except ValueError:
        return None


def _form_values():
    return {
        "name": request.form.get("name", "").strip() or "Пребарување",
        "category_id": _num("category_id") or 159,
        "city_id": _num("city_id"),
        "only_sale": 1 if request.form.get("only_sale") else 0,
        "price_min": _num("price_min"), "price_max": _num("price_max"),
        "m2_min": _num("m2_min", float), "m2_max": _num("m2_max", float),
        "rooms_min": _num("rooms_min", float), "rooms_max": _num("rooms_max", float),
        "include_words": request.form.get("include_words", "").strip(),
        "exclude_words": request.form.get("exclude_words", "").strip(),
        "skip_promoted": 1 if request.form.get("skip_promoted") else 0,
        "max_pages": min(max(_num("max_pages") or 5, 1), 20),
        "notify": 1 if request.form.get("notify") else 0,
        "active": 1 if request.form.get("active") else 0,
    }


@app.route("/searches")
def searches():
    db = get_db()
    rows = db.execute("SELECT * FROM searches ORDER BY id").fetchall()
    counts = {r["search_id"]: r["c"] for r in db.execute(
        "SELECT search_id, COUNT(*) c FROM ads GROUP BY search_id")}
    return render_template("searches.html", searches=rows, counts=counts,
                           search_url=scraper.search_url)


@app.route("/searches/new", methods=["GET", "POST"])
@app.route("/searches/<int:search_id>/edit", methods=["GET", "POST"])
def search_form(search_id=None):
    db = get_db()
    search = None
    if search_id:
        search = db.execute("SELECT * FROM searches WHERE id=?", (search_id,)).fetchone()

    if request.method == "POST":
        v = _form_values()
        cols = list(v.keys())
        if search:
            db.execute(f"UPDATE searches SET {', '.join(c + '=?' for c in cols)}, synced=0"
                       f" WHERE id=?", [*v.values(), search_id])
            # филтрите се сменети: стари огласи што веќе не одговараат се бришат
            db.execute("DELETE FROM ads WHERE search_id=? AND favorite=0", (search_id,))
        else:
            cur = db.execute(f"INSERT INTO searches ({', '.join(cols)}) VALUES"
                             f" ({', '.join('?' * len(cols))})", list(v.values()))
            search_id = cur.lastrowid
        db.commit()
        threading.Thread(target=run_check, args=(search_id,), daemon=True).start()
        flash("Зачувано. Огласите се вчитуваат – освежи ја страницата за неколку секунди.",
              "ok")
        return redirect(url_for("index", search=search_id))

    return render_template("search_form.html", s=search)


@app.post("/searches/<int:search_id>/delete")
def search_delete(search_id):
    db = get_db()
    db.execute("DELETE FROM ads WHERE search_id=?", (search_id,))
    db.execute("DELETE FROM searches WHERE id=?", (search_id,))
    db.commit()
    flash("Пребарувањето е избришано.", "ok")
    return redirect(url_for("searches"))


@app.post("/searches/<int:search_id>/toggle")
def search_toggle(search_id):
    db = get_db()
    db.execute("UPDATE searches SET active=1-active WHERE id=?", (search_id,))
    db.commit()
    return redirect(url_for("searches"))


# ---------------------------------------------------------------- поставки

@app.route("/settings", methods=["GET", "POST"])
def settings():
    db = get_db()
    if request.method == "POST":
        for key in DEFAULT_SETTINGS:
            db.execute("UPDATE settings SET value=? WHERE key=?",
                       (request.form.get(key, "").strip(), key))
        db.commit()
        if request.form.get("test"):
            errors = send_notification(get_settings(db),
                                       "✅ Reklama5 апликацијата работи! "
                                       "Тука ќе добиваш нови огласи.")
            flash("Тест пораката е пратена!" if not errors else " | ".join(errors),
                  "error" if errors else "ok")
        else:
            flash("Поставките се зачувани.", "ok")
        return redirect(url_for("settings"))
    return render_template("settings.html", s=get_settings(db))


# ======================================================================= старт

if __name__ == "__main__":
    init_db()
    threading.Thread(target=scheduler, daemon=True).start()
    print("\n  ➜  Отвори: http://127.0.0.1:5000\n")
    app.run(host="127.0.0.1", port=5000, debug=False)

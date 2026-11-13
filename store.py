import os
import sqlite3
import uuid
from urllib.parse import quote

from flask import (Flask, abort, redirect, render_template, request,
                   send_from_directory, session, url_for)
from jinja2 import DictLoader

# ---------- Change these ----------
SHOP_NAME = "HARSHINI BANGLE'S STORE"
TAGLINE = "Shine in Every Moment"
PHONE = "919948841425"          # WhatsApp number, country code first, no +
EMAIL = "shashankbachu@gmail.com"
CITY = "Dubbak"
ADMIN_PASSWORD = os.environ.get("SHOP_ADMIN_PASSWORD", "ChangeThisPassword")
SECRET_KEY = os.environ.get("SHOP_SECRET_KEY") or os.urandom(32)
# IMPORTANT: Before publishing online, set SHOP_ADMIN_PASSWORD and SHOP_SECRET_KEY
# as environment variables. Do not use the default password in a live store.
# ----------------------------------

UPLOADS = "uploads"
os.makedirs(UPLOADS, exist_ok=True)
app = Flask(__name__)
app.secret_key = SECRET_KEY


def q(sql, args=(), one=False, write=False):
    conn = sqlite3.connect("shop.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, args).fetchall()
    if write:
        conn.commit()
    conn.close()
    if one:
        return rows[0] if rows else None
    return rows


q("""CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
    tagline TEXT, image TEXT, parent_id INTEGER)""", write=True)
q("""CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER NOT NULL,
    name TEXT NOT NULL, price INTEGER, image TEXT, featured INTEGER DEFAULT 0)""",
  write=True)


def save_file(f):
    if not f or not f.filename:
        return None
    ext = f.filename.rsplit(".", 1)[-1].lower()
    if ext not in {"jpg", "jpeg", "png", "webp"}:
        return None
    name = uuid.uuid4().hex + "." + ext
    f.save(os.path.join(UPLOADS, name))
    return name


def remove_file(name):
    path = os.path.join(UPLOADS, name or "")
    if name and os.path.exists(path):
        os.remove(path)


def all_cats():
    return q("""SELECT c.*, p.name AS parent FROM categories c
        LEFT JOIN categories p ON p.id = c.parent_id ORDER BY c.id""")


def need_admin():
    if not session.get("admin"):
        abort(403)


@app.context_processor
def inject():
    def wa(msg):
        return "https://wa.me/" + PHONE + "?text=" + quote(msg)
    return dict(shop=SHOP_NAME, tagline=TAGLINE, email=EMAIL, city=CITY,
                wa=wa, is_admin=session.get("admin"))


# ---------- Customer pages ----------
@app.route("/uploads/<name>")
def uploads(name):
    return send_from_directory(UPLOADS, name)


@app.route("/")
def home():
    cats = q("SELECT * FROM categories WHERE parent_id IS NULL ORDER BY id")
    featured = q("SELECT * FROM products ORDER BY featured DESC, id DESC LIMIT 6")
    return render_template("home.html", cats=cats, featured=featured)


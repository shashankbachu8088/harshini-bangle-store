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
ADMIN_PASSWORD = "HARSHINI.COM"
SECRET_KEY = "hbs-k82jd91xz-dubbak-4471-qw7"
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


@app.route("/category/<int:cid>")
def category(cid):
    cat = q("SELECT * FROM categories WHERE id = ?", (cid,), one=True)
    if not cat:
        abort(404)
    subs = q("SELECT * FROM categories WHERE parent_id = ? ORDER BY name", (cid,))
    sub = request.args.get("sub", type=int)
    if sub:
        items = q("SELECT * FROM products WHERE category_id = ? ORDER BY id DESC", (sub,))
    else:
        items = q("""SELECT * FROM products WHERE category_id = ?
            OR category_id IN (SELECT id FROM categories WHERE parent_id = ?)
            ORDER BY id DESC""", (cid, cid))
    return render_template("category.html", cat=cat, subs=subs, sub=sub, items=items)


# ---------- Admin pages ----------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin"))
        return render_template("admin.html", login=True, error=True)
    if not session.get("admin"):
        return render_template("admin.html", login=True)
    items = q("""SELECT p.*, c.name AS cat FROM products p
        JOIN categories c ON c.id = p.category_id ORDER BY p.id DESC""")
    return render_template("admin.html", login=False, cats=all_cats(), items=items)


@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/admin/category", methods=["POST"])
def add_category():
    need_admin()
    name = request.form.get("name", "").strip()
    if name:
        q("INSERT INTO categories (name, tagline, image, parent_id) VALUES (?, ?, ?, ?)",
          (name, request.form.get("tagline", "").strip(),
           save_file(request.files.get("image")),
           request.form.get("parent_id", type=int)), write=True)
    return redirect(url_for("admin"))


@app.route("/admin/edit-category/<int:cid>", methods=["GET", "POST"])
def edit_category(cid):
    need_admin()
    c = q("SELECT * FROM categories WHERE id = ?", (cid,), one=True)
    if not c:
        abort(404)
    kids = q("SELECT id FROM categories WHERE parent_id = ?", (cid,))
    if request.method == "POST":
        img = c["image"]
        new = save_file(request.files.get("image"))
        if new:
            remove_file(img)
            img = new
        parent = request.form.get("parent_id", type=int)
        if parent == cid or kids:
            parent = None
        q("""UPDATE categories SET name = ?, tagline = ?, image = ?, parent_id = ?
            WHERE id = ?""", (request.form.get("name", "").strip() or c["name"],
                              request.form.get("tagline", "").strip(), img, parent, cid),
          write=True)
        return redirect(url_for("admin"))
    parents = q("SELECT * FROM categories WHERE parent_id IS NULL AND id != ?", (cid,))
    return render_template("edit.html", kind="category", item=c,
                           parents=[] if kids else parents)


@app.route("/admin/delete-category/<int:cid>", methods=["POST"])
def delete_category(cid):
    need_admin()
    used = q("SELECT id FROM products WHERE category_id = ?", (cid,))
    kids = q("SELECT id FROM categories WHERE parent_id = ?", (cid,))
    c = q("SELECT * FROM categories WHERE id = ?", (cid,), one=True)
    if c and not used and not kids:
        remove_file(c["image"])
        q("DELETE FROM categories WHERE id = ?", (cid,), write=True)
    return redirect(url_for("admin"))


@app.route("/admin/product", methods=["POST"])
def add_product():
    need_admin()
    name = request.form.get("name", "").strip()
    cid = request.form.get("category_id", type=int)
    price = request.form.get("price", 0, type=int)
    featured = 1 if request.form.get("featured") else 0
    if name and cid:
        for f in request.files.getlist("photos"):
            fname = save_file(f)
            if fname:
                q("""INSERT INTO products (category_id, name, price, image, featured)
                    VALUES (?, ?, ?, ?, ?)""", (cid, name, price, fname, featured),
                  write=True)
    return redirect(url_for("admin"))


@app.route("/admin/edit-product/<int:pid>", methods=["GET", "POST"])
def edit_product(pid):
    need_admin()
    p = q("SELECT * FROM products WHERE id = ?", (pid,), one=True)
    if not p:
        abort(404)
    if request.method == "POST":
        img = p["image"]
        new = save_file(request.files.get("photo"))
        if new:
            remove_file(img)
            img = new
        q("""UPDATE products SET category_id = ?, name = ?, price = ?,
            image = ?, featured = ? WHERE id = ?""",
          (request.form.get("category_id", type=int),
           request.form.get("name", "").strip() or p["name"],
           request.form.get("price", 0, type=int), img,
           1 if request.form.get("featured") else 0, pid), write=True)
        return redirect(url_for("admin"))
    return render_template("edit.html", kind="product", item=p, cats=all_cats())


@app.route("/admin/delete-product/<int:pid>", methods=["POST"])
def delete_product(pid):
    need_admin()
    p = q("SELECT * FROM products WHERE id = ?", (pid,), one=True)
    if p:
        remove_file(p["image"])
        q("DELETE FROM products WHERE id = ?", (pid,), write=True)
    return redirect(url_for("admin"))


# ---------- Page designs (HTML and CSS) ----------
T = {}

T["base.html"] = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ shop }}</title>
<link href="https://fonts.googleapis.com/css2?family=Dancing+Script:wght@600;700&family=Poppins:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{--pink:#d4187a;--violet:#7a3fe0;--ink:#3b1d4a;--mute:#7b6486;--line:#f0d5ea}
*{box-sizing:border-box}
body{margin:0;font-family:Poppins,sans-serif;color:var(--ink);background:linear-gradient(180deg,#fff8fc,#f5efff);line-height:1.6}
a{color:inherit;text-decoration:none}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px}
.top{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;padding:14px 28px;background:linear-gradient(90deg,#f6d9f0,#e2dbff 55%,#ffe9c9)}
.logo{display:flex;align-items:center;gap:10px}
.mark{display:grid;place-items:center;width:46px;height:46px;border-radius:14px;background:#fff;color:var(--pink);font-size:26px}
.logo b{display:block;font-family:'Dancing Script',cursive;font-size:28px;line-height:1;color:var(--pink)}
.logo small{font-size:12px;color:var(--mute)}
nav{display:flex;gap:6px;background:rgba(255,255,255,.65);padding:6px;border-radius:40px;flex-wrap:wrap}
nav a{padding:8px 18px;border-radius:30px;font-size:14px;font-weight:500}
nav a:hover{background:#fff}
.btn{display:inline-block;padding:11px 26px;border-radius:30px;border:0;color:#fff;font:600 14px Poppins,sans-serif;cursor:pointer;background:linear-gradient(90deg,var(--pink),var(--violet))}
.hero{display:grid;grid-template-columns:1fr 1.2fr;gap:20px;align-items:center;padding:32px 28px;background:radial-gradient(circle at 80% 40%,#ffe8a8,#f9c6e4 45%,#d9ccff);overflow:hidden}
.glass{background:rgba(255,255,255,.7);border:1px solid #fff;border-radius:26px;padding:34px;max-width:480px;justify-self:center}
.glass h1{margin:4px 0;font:700 46px/1.1 'Dancing Script',cursive;color:var(--pink)}
.glass p{margin:6px 0 20px;color:var(--mute)}
.rings{height:300px;display:flex;justify-content:center;align-items:center}
.rings i{display:block;width:120px;height:260px;border-radius:50%;margin-left:-70px;border:12px solid;box-shadow:inset 0 0 0 3px rgba(255,255,255,.55),0 6px 14px rgba(80,20,70,.25)}
section{padding:34px 0}
h2{margin:0 0 4px;font-size:22px}
.sub{margin:0 0 18px;color:var(--mute);font-size:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:18px}
.cat,.card{background:#fff;border-radius:18px;overflow:hidden;border:1px solid var(--line);box-shadow:0 6px 18px rgba(150,60,130,.1)}
.cat-img,.card-img{height:150px;background:linear-gradient(135deg,#ffd3ea,#d9ccff,#ffe2a8) center/cover}
.card-img{height:200px}
.cat-txt,.card-txt{padding:12px 14px}
.cat-txt b,.card-txt b{display:block;font-size:15px}
.cat-txt span{font-size:12px;color:var(--mute)}
.price{color:var(--pink);font-weight:600;margin:2px 0 10px}
.card .btn{width:100%;text-align:center;padding:9px}
.size{display:flex;flex-wrap:wrap;gap:24px;align-items:center;padding:28px;border-radius:26px;background:linear-gradient(110deg,#d8f1f4,#e6dcff 55%,#ffd9ec)}
.chips{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px}
.chips span{padding:6px 16px;border-radius:20px;background:#fff;font-weight:600;font-size:14px}
.chips small{font-weight:400;color:var(--mute)}
.pills{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px}
.pills a{padding:7px 18px;border-radius:20px;background:#fff;border:1px solid var(--line);font-size:14px}
.pills a.on{background:linear-gradient(90deg,var(--pink),var(--violet));color:#fff;border-color:transparent}
footer{margin-top:30px;background:linear-gradient(180deg,#ffe3f3,#f2d7ff);padding:30px 0 0}
.fgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:24px;font-size:14px}
.fgrid h3{margin:0 0 8px;font-size:15px}
.fgrid p{margin:3px 0}
.quote{font:600 22px 'Dancing Script',cursive;color:var(--pink)}
.copy{margin-top:24px;padding:12px;text-align:center;font-size:12px;color:#fff;background:linear-gradient(90deg,#c0399a,#ff7ab8)}
.form{background:#fff;border:1px solid var(--line);border-radius:18px;padding:20px;margin-bottom:22px}
.form input,.form select{width:100%;padding:9px 12px;margin:4px 0 12px;border:1px solid var(--line);border-radius:10px;font:inherit}
.form label{font-size:13px;font-weight:500}
.row{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--line)}
.row img{width:56px;height:56px;object-fit:cover;border-radius:10px}
.row div{flex:1;font-size:14px}
.ed,.del{border:0;padding:6px 14px;border-radius:14px;cursor:pointer;font:500 13px Poppins,sans-serif}
.ed{background:#e7defc;color:#5b2bb8}
.del{background:#fde4ee;color:#b3125e}
@media(max-width:800px){.hero{grid-template-columns:1fr}.rings{height:200px}.rings i{height:170px;width:80px;margin-left:-45px}}
:focus-visible{outline:3px solid var(--violet);outline-offset:2px}
</style></head><body>
<header class="top">
 <a class="logo" href="/"><span class="mark">&#10047;</span><span><b>{{ shop }}</b><small>{{ tagline }}</small></span></a>
 <nav><a href="/">Home</a><a href="/#categories">Shop</a><a href="/#size">Size Finder</a><a href="#contact">Contact</a>{% if is_admin %}<a href="/admin">Admin Panel</a>{% endif %}</nav>
 <a class="btn" href="{{ wa('Hello, I have a question about your bangles') }}">Chat on WhatsApp</a>
</header>
{% block body %}{% endblock %}
<footer id="contact"><div class="wrap"><div class="fgrid">
  <div><h3>Quick Links</h3><p><a href="/">Home</a></p><p><a href="/#categories">Shop</a></p><p><a href="/#size">Size Finder</a></p></div>
  <div><h3>Contact Us</h3><p>{{ email }}</p><p>{{ city }}</p><p><a href="{{ wa('Hello') }}">Message on WhatsApp</a></p></div>
  <div><p class="quote">Because every hand deserves the perfect bangle.</p></div>
 </div></div>
 <div class="copy">&copy; {{ shop }}. All rights reserved.</div>
</footer></body></html>"""

T["home.html"] = """{% extends "base.html" %}{% block body %}
<div class="hero">
 <div class="glass"><b>Welcome to</b><h1>{{ shop }}</h1>
  <p><b>Traditional Elegance &amp; Modern Style</b><br>Beautiful bangles for every mood, every outfit, and every special moment.</p>
  <a class="btn" href="#categories">Shop now</a></div>
 <div class="rings" aria-hidden="true">
  <i style="border-color:#e91e8c"></i><i style="border-color:#f4b400"></i><i style="border-color:#0aa6c9"></i>
  <i style="border-color:#2e9e4f"></i><i style="border-color:#7b3fe4"></i><i style="border-color:#e91e8c"></i></div>
</div>
<div class="wrap">
 <section id="categories"><h2>Shop by category</h2><p class="sub">Find your perfect style</p>
  {% if not cats %}<p class="sub">Categories will appear here soon.</p>{% endif %}
  <div class="grid">{% for c in cats %}
   <a class="cat" href="{{ url_for('category', cid=c.id) }}">
    <div class="cat-img" {% if c.image %}style="background-image:url('{{ url_for('uploads', name=c.image) }}')"{% endif %}></div>
    <div class="cat-txt"><b>{{ c.name }}</b><span>{{ c.tagline or '' }}</span></div></a>{% endfor %}</div></section>
 <section id="size"><div class="size"><div style="flex:1;min-width:260px">
   <h2>Not sure about your bangle size?</h2>
   <p class="sub">Send us a photo of your hand on WhatsApp and we will suggest the right size.</p>
   <a class="btn" href="{{ wa('Hello, please help me find my bangle size') }}">Ask for size help</a></div>
  <div><b>Recommended sizes</b><div class="chips"><span>2-4 <small>Small</small></span><span>2-6 <small>Medium</small></span><span>2-8 <small>Large</small></span><span>2-10 <small>Extra large</small></span></div></div></div></section>
 {% if featured %}<section><h2>Featured designs</h2><p class="sub">Our most loved designs</p>
  <div class="grid">{% for p in featured %}
   <div class="card"><div class="card-img" style="background-image:url('{{ url_for('uploads', name=p.image) }}')"></div>
    <div class="card-txt"><b>{{ p.name }}</b>{% if p.price %}<div class="price">&#8377; {{ p.price }}</div>{% endif %}
    <a class="btn" href="{{ wa('Hello, I want to order: ' ~ p.name) }}">Order on WhatsApp</a></div></div>{% endfor %}</div></section>{% endif %}
</div>{% endblock %}"""

T["category.html"] = """{% extends "base.html" %}{% block body %}
<div class="wrap"><section><h2>{{ cat.name }}</h2><p class="sub">{{ cat.tagline or '' }}</p>
 {% if subs %}<div class="pills"><a href="{{ url_for('category', cid=cat.id) }}" class="{{ '' if sub else 'on' }}">All</a>
  {% for s in subs %}<a href="{{ url_for('category', cid=cat.id, sub=s.id) }}" class="{{ 'on' if sub == s.id else '' }}">{{ s.name }}</a>{% endfor %}</div>{% endif %}
 {% if not items %}<p class="sub">No designs here yet. Please check back soon.</p>{% endif %}
 <div class="grid">{% for p in items %}
  <div class="card"><div class="card-img" style="background-image:url('{{ url_for('uploads', name=p.image) }}')"></div>
   <div class="card-txt"><b>{{ p.name }}</b>{% if p.price %}<div class="price">&#8377; {{ p.price }}</div>{% endif %}
   <a class="btn" href="{{ wa('Hello, I want to order: ' ~ p.name) }}">Order on WhatsApp</a></div></div>{% endfor %}</div>
</section></div>{% endblock %}"""

T["admin.html"] = """{% extends "base.html" %}{% block body %}
<div class="wrap"><section><h2>Admin Panel</h2>
{% if login %}
 <form class="form" method="post" style="max-width:360px"><label>Password</label>
  <input type="password" name="password" autofocus>
  {% if error %}<p style="color:#b3125e">Wrong password. Try again.</p>{% endif %}
  <button class="btn">Log in</button></form>
{% else %}
 <p><a href="/admin/logout"><b>Log out</b></a></p>
 <form class="form" method="post" action="/admin/category" enctype="multipart/form-data"><b>1. Create a section</b><br>
  <label>Section name</label><input name="name" required>
  <label>Short line under the name (optional)</label><input name="tagline">
  <label>Put it inside</label><select name="parent_id"><option value="">Main section</option>
   {% for c in cats if not c.parent_id %}<option value="{{ c.id }}">{{ c.name }}</option>{% endfor %}</select>
  <label>Cover photo (optional)</label><input type="file" name="image" accept="image/*">
  <button class="btn">Create section</button></form>
 <form class="form" method="post" action="/admin/product" enctype="multipart/form-data"><b>2. Upload photos</b><br>
  <label>Section</label><select name="category_id" required>
   {% for c in cats %}<option value="{{ c.id }}">{{ (c.parent ~ ' > ') if c.parent else '' }}{{ c.name }}</option>{% endfor %}</select>
  <label>Item name</label><input name="name" required>
  <label>Price in rupees</label><input type="number" name="price" min="0" value="0">
  <label>Photos (you can choose many)</label><input type="file" name="photos" accept="image/*" multiple required>
  <label><input type="checkbox" name="featured" style="width:auto"> Show on the home page</label><br><br>
  <button class="btn">Save photos</button></form>
 <h2>Sections</h2>
 {% for c in cats %}<div class="row"><div>{{ (c.parent ~ ' > ') if c.parent else '' }}<b>{{ c.name }}</b></div>
  <a class="ed" href="/admin/edit-category/{{ c.id }}">Edit</a>
  <form method="post" action="/admin/delete-category/{{ c.id }}" onsubmit="return confirm('Delete this section?')"><button class="del">Delete</button></form></div>{% endfor %}
 <p class="sub">A section can be deleted only when it has no photos and no sub-sections.</p>
 <h2>Photos</h2>
 {% for p in items %}<div class="row"><img src="{{ url_for('uploads', name=p.image) }}" alt="">
  <div><b>{{ p.name }}</b><br>{{ p.cat }} &middot; &#8377; {{ p.price }}{% if p.featured %} &middot; On home page{% endif %}</div>
  <a class="ed" href="/admin/edit-product/{{ p.id }}">Edit</a>
  <form method="post" action="/admin/delete-product/{{ p.id }}" onsubmit="return confirm('Delete this photo?')"><button class="del">Delete</button></form></div>{% endfor %}
{% endif %}</section></div>{% endblock %}"""

T["edit.html"] = """{% extends "base.html" %}{% block body %}
<div class="wrap"><section><h2>Edit {{ kind }}</h2>
<form class="form" method="post" enctype="multipart/form-data" style="max-width:520px">
 <label>Name</label><input name="name" value="{{ item.name }}" required>
 {% if kind == 'category' %}
  <label>Short line</label><input name="tagline" value="{{ item.tagline or '' }}">
  <label>Put it inside</label><select name="parent_id"><option value="">Main section</option>
   {% for c in parents %}<option value="{{ c.id }}" {% if c.id == item.parent_id %}selected{% endif %}>{{ c.name }}</option>{% endfor %}</select>
  {% if item.image %}<img src="{{ url_for('uploads', name=item.image) }}" width="120" alt=""><br>{% endif %}
  <label>New cover photo (optional)</label><input type="file" name="image" accept="image/*">
 {% else %}
  <label>Price in rupees</label><input type="number" name="price" min="0" value="{{ item.price }}">
  <label>Section</label><select name="category_id">
   {% for c in cats %}<option value="{{ c.id }}" {% if c.id == item.category_id %}selected{% endif %}>{{ (c.parent ~ ' > ') if c.parent else '' }}{{ c.name }}</option>{% endfor %}</select>
  <label><input type="checkbox" name="featured" style="width:auto" {% if item.featured %}checked{% endif %}> Show on the home page</label><br><br>
  <img src="{{ url_for('uploads', name=item.image) }}" width="160" alt=""><br>
  <label>Replace photo (optional)</label><input type="file" name="photo" accept="image/*">
 {% endif %}
 <button class="btn">Save changes</button> &nbsp; <a href="/admin">Cancel</a>
</form></section></div>{% endblock %}"""

app.jinja_loader = DictLoader(T)

if __name__ == "__main__":
    app.run(debug=True)

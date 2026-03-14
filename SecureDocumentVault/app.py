import os
import psycopg2
from psycopg2.extras import DictCursor
import cloudinary
import cloudinary.uploader
from flask import Flask, render_template, request, redirect, session, jsonify, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "tvs_vault_secure_2026")

# --- 1. Cloudinary Configuration ---
# Render Environment Variables లో ఈ వివరాలు సెట్ చేసుకోవాలి
cloudinary.config( 
  cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME"), 
  api_key = os.environ.get("CLOUDINARY_API_KEY"), 
  api_secret = os.environ.get("CLOUDINARY_API_SECRET") 
)

# --- 2. Database Connection (PostgreSQL) ---
def get_db_connection():
    # Render లో లభించే External Database URL ని ఇక్కడ వాడాలి
    DB_URL = os.environ.get("DATABASE_URL")
    conn = psycopg2.connect(DB_URL, sslmode='require')
    return conn

# టేబుల్స్ క్రియేషన్
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS documents(
        id SERIAL PRIMARY KEY,
        user_name TEXT,
        name TEXT,
        file_url TEXT,
        public_id TEXT,
        password TEXT
    )
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

# --- 3. Routes ---

@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            session["user"] = username
            return redirect(url_for("dashboard"))
        return "Invalid Credentials"
    return render_template("login.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("INSERT INTO users(username, password) VALUES(%s, %s)", (username, password))
            conn.commit()
            cur.close()
            conn.close()
            return redirect(url_for("login"))
        except:
            return "User already exists"
    return render_template("register.html")

@app.route("/dashboard", methods=["GET","POST"])
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)

    if request.method == "POST":
        docname = request.form["docname"]
        docpass = request.form["docpass"]
        file = request.files["file"]

        if file:
            # Cloudinary కి అప్‌లోడ్ చేయడం
            upload_result = cloudinary.uploader.upload(file)
            file_url = upload_result["secure_url"]
            public_id = upload_result["public_id"]

            cur.execute("INSERT INTO documents(user_name, name, file_url, public_id, password) VALUES(%s, %s, %s, %s, %s)",
                        (session["user"], docname, file_url, public_id, docpass))
            conn.commit()

    cur.execute("SELECT * FROM documents WHERE user_name=%s", (session["user"],))
    docs = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("dashboard.html", docs=docs)

@app.route("/check_password", methods=["POST"])
def check_password():
    docid = request.form["docid"]
    password = request.form["password"]

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    cur.execute("SELECT password, file_url FROM documents WHERE id=%s", (docid,))
    data = cur.fetchone()
    cur.close()
    conn.close()

    if data and data['password'] == password:
        return jsonify({"status": "success", "file": data['file_url']})
    else:
        return jsonify({"status": "fail"})

@app.route("/delete/<int:id>")
def delete(id):
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    
    # Cloudinary నుండి ఫైల్ డిలీట్ చేయడానికి public_id పొందడం
    cur.execute("SELECT public_id FROM documents WHERE id=%s", (id,))
    doc = cur.fetchone()
    
    if doc:
        cloudinary.uploader.destroy(doc['public_id'])
        cur.execute("DELETE FROM documents WHERE id=%s", (id,))
        conn.commit()
    
    cur.close()
    conn.close()
    return redirect(url_for("dashboard"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)

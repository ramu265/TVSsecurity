import os
import psycopg2
from psycopg2.extras import DictCursor
import cloudinary
import cloudinary.uploader
from flask import Flask, render_template, request, redirect, session, jsonify, url_for

app = Flask(__name__)
# Render Environment Variables లో SECRET_KEY సెట్ చేసుకోవాలి
app.secret_key = os.environ.get("SECRET_KEY", "tvs_vault_secure_2026")

# --- 1. Cloudinary Configuration ---
cloudinary.config( 
    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME"), 
    api_key = os.environ.get("CLOUDINARY_API_KEY"), 
    api_secret = os.environ.get("CLOUDINARY_API_SECRET") 
)

# --- 2. Database Connection (PostgreSQL) ---
def get_db_connection():
    # Render లో లభించే Database URL ని తీసుకుంటుంది
    DB_URL = os.environ.get("DATABASE_URL")
    
    # ఒకవేళ URL 'postgresql://' తో ఉంటే దాన్ని 'postgres://' గా మారుస్తుంది (Render/Python compatibility కోసం)
    if DB_URL and DB_URL.startswith("postgresql://"):
        DB_URL = DB_URL.replace("postgresql://", "postgres://", 1)
        
    conn = psycopg2.connect(DB_URL, sslmode='require')
    return conn

# టేబుల్స్ క్రియేషన్
def init_db():
    try:
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
    except Exception as e:
        print(f"Database Error: {e}")

# యాప్ స్టార్ట్ అవ్వగానే డేటాబేస్ టేబుల్స్ క్రియేట్ అవుతాయి
init_db()

# --- 3. Routes ---

# Home Route: వెబ్‌సైట్ ఓపెన్ అవ్వగానే లాగిన్ పేజీకి పంపుతుంది
@app.route("/", methods=["GET", "POST"])
def home():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/login", methods=["GET", "POST"])
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
        return "Invalid Credentials. <a href='/login'>Try again</a>"
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
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
            return "User already exists. <a href='/register'>Try again</a>"
    return render_template("register.html")

@app.route("/dashboard", methods=["GET", "POST"])
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
            upload_result = cloudinary.uploader.upload(file)
            file_url = upload_result["secure_url"]
            public_id = upload_result["public_id"]

            cur.execute("INSERT INTO documents(user_name, name, file_url, public_id, password) VALUES(%s, %s, %s, %s, %s)",
                        (session["user"], docname, file_url, public_id, docpass))
            conn.commit()
            return redirect(url_for("dashboard"))

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
    # Render కోసం హోస్ట్ మరియు పోర్ట్ సెట్టింగ్స్
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

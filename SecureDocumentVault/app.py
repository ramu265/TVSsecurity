import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --- Configuration Changes for Deployment ---
# Secret Key ni Environment Variable nundi techukuntundi
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'my_secure_vault_key_2026')

# Database Path Fix: Render lo error rakunda absolute path set chesam
base_dir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'vault.db')

# Uploads Folder Path Fix
app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'static', 'uploads')

# Folder lekapothe create chesthundhi
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Database Models ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    docs = db.relationship('Document', backref='owner', lazy=True)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    doc_password = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    # Query.get() badulu session.get() use cheyadam 2.0 standard
    return db.session.get(User, int(user_id))

# --- Routes ---

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        uname = request.form.get('username')
        pwd = request.form.get('password')
        if User.query.filter_by(username=uname).first():
            flash('Username already exists!')
            return redirect(url_for('register'))
        new_user = User(username=uname, password=pwd)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.password == request.form.get('password'):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid Credentials! Try again.')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', docs=current_user.docs)

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    doc_name = request.form.get('doc_name')
    doc_pass = request.form.get('doc_pass')
    file = request.files.get('file')
    
    if file and file.filename != '':
        fname = secure_filename(file.filename)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
        file.save(save_path)
        
        new_doc = Document(name=doc_name, filename=fname, doc_password=doc_pass, user_id=current_user.id)
        db.session.add(new_doc)
        db.session.commit()
        flash('Document uploaded successfully!')
    else:
        flash('No file selected!')
    return redirect(url_for('dashboard'))

@app.route('/access/<int:doc_id>', methods=['POST'])
@login_required
def access(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc:
        flash("Document not found!")
        return redirect(url_for('dashboard'))
        
    entered_pass = request.form.get('check_pass')
    if doc.doc_password == entered_pass:
        return render_template('view_file.html', doc=doc)
    flash('Incorrect Document Password!')
    return redirect(url_for('dashboard'))

@app.route('/delete/<int:doc_id>')
@login_required
def delete(doc_id):
    doc = db.session.get(Document, doc_id)
    if doc and doc.user_id == current_user.id:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], doc.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        db.session.delete(doc)
        db.session.commit()
        flash('Document deleted successfully.')
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

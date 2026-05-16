from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import os
import secrets
from dotenv import load_dotenv
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta, datetime
from whitenoise import WhiteNoise

load_dotenv()

app = Flask(__name__)
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/', prefix='static/')

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'unirok-innovations-super-secret')
db_url = os.environ.get('DATABASE_URL', 'sqlite:///unirok.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

db = SQLAlchemy(app)

# --- Database Models ---

class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    brand_color = db.Column(db.String(20), default='#D4AF37') # Default Gold
    
    products = db.relationship('Product', backref='company', lazy=True, cascade="all, delete-orphan")

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    image_url = db.Column(db.String(255), nullable=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)

class BlogPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SiteSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

# --- CLI Command to Seed Data ---
@app.cli.command('seed-db')
def seed_db():
    db.create_all()
    if not Company.query.first():
        c1 = Company(name='Myk Laticrete', slug='myk-laticrete', description='Premium adhesives, grouts, and waterproofing solutions.', brand_color='#E53935') # Red
        c2 = Company(name='Godrej', slug='godrej', description='Leading security solutions and premium locks.', brand_color='#1E88E5') # Blue
        c3 = Company(name='UltraTech', slug='ultratech', description='The engineer\'s choice. High quality cement and building materials.', brand_color='#D4AF37') # Gold
        
        db.session.add_all([c1, c2, c3])
        db.session.commit()
        
        p1 = Product(name='Laticrete Grout', company_id=c1.id, image_url='https://placehold.co/400x300/e53935/ffffff?text=Laticrete+Grout')
        p2 = Product(name='Laticrete Adhesive', company_id=c1.id, image_url='https://placehold.co/400x300/e53935/ffffff?text=Adhesive')
        p3 = Product(name='Godrej Nav-Tal Padlock', company_id=c2.id, image_url='https://placehold.co/400x300/1e88e5/ffffff?text=Godrej+Lock')
        p4 = Product(name='UltraTech Premium Cement', company_id=c3.id, image_url='https://placehold.co/400x300/d4af37/ffffff?text=UltraTech')
        
        db.session.add_all([p1, p2, p3, p4])
        db.session.commit()
    
        if not SiteSetting.query.filter_by(key="google_form_url").first():
            db.session.add(SiteSetting(key="google_form_url", value="https://docs.google.com/forms/d/e/1FAIpQLSeNQeiQRZuZNivV_xXvGax3PfclB-UtFPEuXuQ5JOwjXbdXtA/viewform?usp=publish-editor"))
            db.session.commit()
            
        print("Database seeded successfully with initial dummy data.")
    else:
        print("Database already contains data.")

# --- Public Routes ---

@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = session.get('csrf_token', None)
        if not token or token != request.form.get('csrf_token'):
            flash('Invalid CSRF token or session expired. Please try again.', 'error')
            return redirect(request.referrer or url_for('index'))
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)



@app.route('/')
def index():
    companies = Company.query.all()
    return render_template('index.html', companies=companies)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/companies/<slug>')
def company(slug):
    company = Company.query.filter_by(slug=slug).first_or_404()
    return render_template('company.html', company=company)

@app.route('/contact')
def contact():
    setting = SiteSetting.query.filter_by(key="google_form_url").first()
    google_form_url = setting.value if setting else "https://docs.google.com/forms/d/e/1FAIpQLSeNQeiQRZuZNivV_xXvGax3PfclB-UtFPEuXuQ5JOwjXbdXtA/viewform?usp=publish-editor"
    return render_template('contact.html', google_form_url=google_form_url)

@app.route('/robots.txt')
def robots():
    return app.send_static_file('robots.txt')

@app.route('/sitemap.xml')
def sitemap():
    from flask import Response
    companies = Company.query.all()
    posts = BlogPost.query.all()
    xml = render_template('sitemap.xml', companies=companies, posts=posts)
    return Response(xml, mimetype='application/xml')

# --- Blog Routes ---

@app.route('/blog')
def blog_index():
    posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
    return render_template('blog_index.html', posts=posts)

@app.route('/blog/<slug>')
def blog_post(slug):
    post = BlogPost.query.filter_by(slug=slug).first_or_404()
    return render_template('blog_post.html', post=post)

# --- Client Routes ---

@app.route('/client/register', methods=['GET', 'POST'])
def client_register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if Client.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
        else:
            new_client = Client(email=email, password_hash=generate_password_hash(password))
            db.session.add(new_client)
            db.session.commit()
            flash('Registration successful! You may now login.', 'success')
            return redirect(url_for('client_login'))
    return render_template('client_register.html')

@app.route('/client/login', methods=['GET', 'POST'])
def client_login():
    if request.method == 'POST':
        client = Client.query.filter_by(email=request.form['email']).first()
        if client and check_password_hash(client.password_hash, request.form['password']):
            session['client_id'] = client.id
            return redirect(url_for('client_dashboard'))
        else:
            flash('Invalid email or password', 'error')
    return render_template('client_login.html')

@app.route('/client/logout')
def client_logout():
    session.pop('client_id', None)
    return redirect(url_for('index'))

@app.route('/client/dashboard')
def client_dashboard():
    if 'client_id' not in session:
        return redirect(url_for('client_login'))
    client = Client.query.get(session['client_id'])
    return render_template('client_dashboard.html', client=client)

# --- Admin / CMS Routes ---

ADMIN_PASSWORD_HASH = generate_password_hash(os.environ.get("ADMIN_PASSWORD", "admin")) # Overridable via env variables

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if check_password_hash(ADMIN_PASSWORD_HASH, request.form['password']):
            session.permanent = True
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid password', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))

@app.route('/admin')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    companies = Company.query.all()
    posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
    form_setting = SiteSetting.query.filter_by(key="google_form_url").first()
    return render_template('admin_dashboard.html', companies=companies, posts=posts, form_setting=form_setting)

@app.route('/admin/company/add', methods=['POST'])
def admin_add_company():
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    
    name = request.form['name']
    slug = name.lower().replace(' ', '-')
    desc = request.form.get('description', '')
    color = request.form.get('brand_color', '#D4AF37')
    
    original_slug = slug
    counter = 1
    while Company.query.filter_by(slug=slug).first():
        slug = f"{original_slug}-{counter}"
        counter += 1

    new_company = Company(name=name, slug=slug, description=desc, brand_color=color)
    try:
        db.session.add(new_company)
        db.session.commit()
        flash('Company added successfully!', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Database error occurred. Please try again.', 'error')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/company/delete/<int:id>', methods=['POST'])
def admin_delete_company(id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    
    company = Company.query.get_or_404(id)
    db.session.delete(company)
    db.session.commit()
    flash('Company deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/product/add', methods=['POST'])
def admin_add_product():
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    
    name = request.form['name']
    company_id = request.form['company_id']
    image_url = request.form.get('image_url', '')
    
    new_product = Product(name=name, company_id=company_id, image_url=image_url)
    db.session.add(new_product)
    db.session.commit()
    flash('Product added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/settings/update', methods=['POST'])
def admin_update_settings():
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    
    form_url = request.form.get('google_form_url', '')
    setting = SiteSetting.query.filter_by(key="google_form_url").first()
    if setting:
        setting.value = form_url
    else:
        db.session.add(SiteSetting(key="google_form_url", value=form_url))
    db.session.commit()
    flash("Settings updated successfully!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/blog/add', methods=['POST'])
def admin_add_blog():
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    
    title = request.form['title']
    slug = title.lower().replace(' ', '-')
    content = request.form['content']
    
    original_slug = slug
    counter = 1
    while BlogPost.query.filter_by(slug=slug).first():
        slug = f"{original_slug}-{counter}"
        counter += 1

    new_post = BlogPost(title=title, slug=slug, content=content)
    db.session.add(new_post)
    db.session.commit()
    flash('Blog post published!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/blog/delete/<int:id>', methods=['POST'])
def admin_delete_blog(id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    
    post = BlogPost.query.get_or_404(id)
    db.session.delete(post)
    db.session.commit()
    flash('Blog post deleted!', 'success')
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)

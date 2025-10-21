from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import os

# --- Configuration ---
app = Flask(__name__)
# IMPORTANT: In a production environment like Render, FLASK_SECRET_KEY must be set
# via environment variables.
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key_if_not_set') 
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///muse.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Admin Credentials (Read from environment variables set on Render) ---
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'password123')

# --- Database Models ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False) # Plain text for simplicity
    orders = db.relationship('Order', backref='customer', lazy=True)
    def __repr__(self):
        return f'<User {self.username}>'

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False) # Stored in Rupees (₹)
    stock = db.Column(db.Integer, nullable=False)
    image = db.Column(db.String(200), default='default.jpg')
    category = db.Column(db.String(50), default='Other') 

    def __repr__(self):
        return f'<Product {self.name}>'

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    products_json = db.Column(db.Text, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Pending')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    def __repr__(self):
        return f'<Order {self.id}>'
    def get_products(self):
        return json.loads(self.products_json)

# --- Initial Setup and Seeding ---

def init_db():
    """Creates the database and adds initial data/admin credentials."""
    # NOTE: This function is called manually via the Render Shell.
    with app.app_context():
        # Only attempt to create if tables don't exist
        db.create_all()
        
        # Check if sample data already exists (prevents duplicates)
        if Product.query.count() == 0:
            print("Seeding sample data...")
            sample_products = [
                Product(name='Rose Gold Heart Pendant', description='A delicate rose gold heart pendant with small stones.', price=1499.00, stock=15, image='pendant_heart.jpg', category='Pendant Sets'),
                Product(name='Sapphire Stud Earrings', description='Small but striking sapphire earrings for daily wear.', price=750.50, stock=30, image='earrings.jpg', category='Earrings'),
                Product(name='Classic Diamond Necklace Set', description='Full bridal-style necklace set with matching earrings.', price=2999.00, stock=10, image='necklace_classic.jpg', category='Necklace Sets'),
                Product(name='Emerald Drop Earrings', description='Elegant emerald cut drop earrings, perfect for evenings.', price=1250.00, stock=20, image='earrings_emerald.jpg', category='Earrings'),
                Product(name='Solitaire Pendant & Chain', description='Simple solitaire pendant with a thin golden chain.', price=1800.00, stock=12, image='pendant_solitaire.jpg', category='Pendant Sets'),
                Product(name='Pearl Choker Necklace', description='A modern choker-style necklace with tiny freshwater pearls.', price=2400.00, stock=8, image='necklace_pearl.jpg', category='Necklace Sets'),
            ]
            db.session.add_all(sample_products)
            db.session.commit()
            print("Sample products added.")

# --- Helper Functions ---

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('is_admin') != True:
            flash('Admin access required.', 'danger')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- User Authentication Routes ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not username or not email or not password:
            flash('All fields are required.', 'danger')
            return render_template('register.html')

        user_exists = User.query.filter((User.username == username) | (User.email == email)).first()
        if user_exists:
            flash('Username or Email already taken.', 'danger')
            return render_template('register.html')

        new_user = User(username=username, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.password == password:
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
            return render_template('login.html')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('cart', None) 
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# --- User Product & Shopping Cart Routes ---

@app.route('/')
def index():
    products = Product.query.limit(3).all() 
    return render_template('index.html', products=products)

@app.route('/shop')
def shop():
    all_products = Product.query.all()
    
    categorized_products = {}
    for product in all_products:
        category = product.category
        if category not in categorized_products:
            categorized_products[category] = []
        categorized_products[category].append(product)
        
    category_order = ['Pendant Sets', 'Necklace Sets', 'Earrings']
    
    return render_template('shop.html', 
                           categorized_products=categorized_products,
                           category_order=category_order)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('product_detail.html', product=product)

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'user_id' not in session:
        flash('Please log in to add items to your cart.', 'warning')
        return redirect(url_for('login'))
        
    product = Product.query.get_or_404(product_id)
    quantity = int(request.form.get('quantity', 1))

    if product.stock < quantity:
        flash(f'Cannot add {quantity} of {product.name}. Only {product.stock} left in stock.', 'danger')
        return redirect(url_for('shop'))

    cart = session.get('cart', {})
    
    if str(product_id) in cart:
        cart[str(product_id)]['quantity'] += quantity
    else:
        cart[str(product_id)] = {
            'name': product.name,
            'price': product.price,
            'image': product.image,
            'quantity': quantity
        }
    
    session['cart'] = cart
    flash(f'{quantity} x {product.name} added to cart!', 'success')
    return redirect(url_for('cart'))

@app.route('/cart')
def cart():
    if 'user_id' not in session:
        flash('Please log in to view your cart.', 'warning')
        return redirect(url_for('login'))
        
    cart_items = session.get('cart', {})
    total_price = sum(item['price'] * item['quantity'] for item in cart_items.values())
    
    cleaned_cart = {}
    for product_id_str, item in cart_items.items():
        product = Product.query.get(int(product_id_str))
        if product and product.stock >= item['quantity']:
            cleaned_cart[product_id_str] = item
        elif product and product.stock > 0:
            item['quantity'] = product.stock
            cleaned_cart[product_id_str] = item
            flash(f'Adjusted quantity of {product.name} to {product.stock} due to stock changes.', 'warning')
        else:
            flash(f'{item["name"]} was removed from your cart as it is out of stock.', 'danger')
            
    session['cart'] = cleaned_cart 
    total_price = sum(item['price'] * item['quantity'] for item in cleaned_cart.values())

    return render_template('cart.html', cart_items=cleaned_cart, total_price=total_price)

@app.route('/update_cart/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cart = session.get('cart', {})
    action = request.form.get('action')
    product_id_str = str(product_id)
    product = Product.query.get_or_404(product_id)

    if product_id_str in cart:
        if action == 'remove':
            cart.pop(product_id_str)
            flash(f'{product.name} removed from cart.', 'info')
        elif action == 'increase':
            if cart[product_id_str]['quantity'] < product.stock:
                cart[product_id_str]['quantity'] += 1
                flash(f'Quantity of {product.name} increased.', 'success')
            else:
                flash(f'Maximum stock ({product.stock}) reached for {product.name}.', 'danger')
        elif action == 'decrease':
            cart[product_id_str]['quantity'] -= 1
            if cart[product_id_str]['quantity'] <= 0:
                cart.pop(product_id_str)
                flash(f'{product.name} removed from cart.', 'info')
            else:
                flash(f'Quantity of {product.name} decreased.', 'success')

        session['cart'] = cart
        session.modified = True
    return redirect(url_for('cart'))

# --- CHECKOUT ROUTE (SIMULATED PAYMENT) ---

@app.route('/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session:
        flash('Please log in to checkout.', 'warning')
        return redirect(url_for('login'))
    
    cart = session.get('cart', {})
    if not cart:
        flash('Your cart is empty.', 'danger')
        return redirect(url_for('cart'))

    user_id = session['user_id']
    total_price = 0
    order_products = {}
    
    # Check stock and calculate total price
    for product_id_str, item in cart.items():
        product_id = int(product_id_str)
        product = Product.query.get(product_id)
        quantity = item['quantity']
        
        if not product or product.stock < quantity:
            flash(f'Cannot proceed with checkout. Stock insufficient for {item["name"]}.', 'danger')
            return redirect(url_for('cart'))

        total_price += item['price'] * quantity
        order_products[product_id_str] = {
            'quantity': quantity,
            'price_at_order': item['price'], 
            'name': item['name']
        }
        
        # Decrement stock
        product.stock -= quantity
        db.session.add(product)

    # Create the Order
    new_order = Order(
        user_id=user_id,
        products_json=json.dumps(order_products),
        total_price=total_price,
        status='Pending' 
    )
    db.session.add(new_order)
    db.session.commit()
    
    # Clear the cart after placing the order
    session.pop('cart', None) 

    flash(f'Order #{new_order.id} placed successfully. Total: ₹{total_price:.2f}. Simulating immediate payment success.', 'success')
    
    # Simulate payment completion and update status immediately
    new_order.status = 'Completed'
    db.session.commit()
    
    flash(f'Payment successful. Order #{new_order.id} status updated to Completed.', 'success')
    return redirect(url_for('order_history'))


@app.route('/order_history')
def order_history():
    if 'user_id' not in session:
        flash('Please log in to view your orders.', 'warning')
        return redirect(url_for('login'))
        
    orders = Order.query.filter_by(user_id=session['user_id']).order_by(Order.timestamp.desc()).all()
    
    return render_template('order_history.html', orders=orders, json_load=json.loads)

# --- Admin Routes (CRUD operations) ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Use credentials from environment variables
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['is_admin'] = True
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials.', 'danger')
            return render_template('admin/admin_login.html')
            
    return render_template('admin/admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    flash('Admin logged out.', 'info')
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    total_products = Product.query.count()
    pending_orders = Order.query.filter_by(status='Pending').count()
    completed_orders = Order.query.filter_by(status='Completed').count()
    
    recent_orders = Order.query.order_by(Order.timestamp.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html', 
        total_products=total_products, 
        pending_orders=pending_orders, 
        completed_orders=completed_orders,
        recent_orders=recent_orders
    )

@app.route('/admin/products', methods=['GET', 'POST'])
@admin_required
def manage_products():
    categories = ['Pendant Sets', 'Necklace Sets', 'Earrings', 'Other']
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            description = request.form.get('description')
            price = float(request.form.get('price'))
            stock = int(request.form.get('stock'))
            image = request.form.get('image', 'default.jpg')
            category = request.form.get('category', 'Other') 

            new_product = Product(name=name, description=description, price=price, stock=stock, image=image, category=category)
            db.session.add(new_product)
            db.session.commit()
            flash(f'Product "{name}" added successfully.', 'success')
        except ValueError:
            flash('Invalid input for price or stock.', 'danger')
        return redirect(url_for('manage_products'))

    products = Product.query.all()
    return render_template('admin/manage_products.html', products=products, categories=categories)

@app.route('/admin/product/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    categories = ['Pendant Sets', 'Necklace Sets', 'Earrings', 'Other'] 
    if request.method == 'POST':
        try:
            product.name = request.form.get('name')
            product.description = request.form.get('description')
            product.price = float(request.form.get('price'))
            product.stock = int(request.form.get('stock'))
            product.image = request.form.get('image')
            product.category = request.form.get('category') 
            
            db.session.commit()
            flash(f'Product "{product.name}" updated successfully.', 'success')
            return redirect(url_for('manage_products'))
        except ValueError:
            flash('Invalid input for price or stock.', 'danger')

    return render_template('admin/edit_product.html', product=product, categories=categories)

@app.route('/admin/product/delete/<int:product_id>', methods=['POST'])
@admin_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    db.session.delete(product)
    db.session.commit()
    flash(f'Product "{product.name}" deleted.', 'info')
    return redirect(url_for('manage_products'))

@app.route('/admin/orders')
@admin_required
def manage_orders():
    orders = Order.query.order_by(Order.timestamp.desc()).all()
    return render_template('admin/manage_orders.html', orders=orders, json_load=json.loads)

@app.route('/admin/order/update_status/<int:order_id>', methods=['POST'])
@admin_required
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    
    if new_status in ['Pending', 'Completed', 'Cancelled']:
        order.status = new_status
        db.session.commit()
        flash(f'Order #{order.id} status updated to {new_status}.', 'success')
    else:
        flash('Invalid status provided.', 'danger')
        
    return redirect(url_for('manage_orders'))


# --- Run Application (For local development) ---
if __name__ == '__main__':
    # Initialize DB (create tables and sample data) only if run locally
    init_db()
    app.run(debug=True)
    # NOTE: Gunicorn handles production startup via the Dockerfile
from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from config import MYSQL_CONFIG, SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY

def get_db():
    return mysql.connector.connect(**MYSQL_CONFIG)

@app.route('/')
def home():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products LIMIT 8")
    products = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('home.html', products=products)

@app.route('/products')
def products():
    category = request.args.get('category')
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if category:
        cursor.execute("SELECT * FROM products WHERE category=%s", (category,))
    else:
        cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('products.html', products=products, category=category)

@app.route('/product/<int:product_id>', methods=['GET', 'POST'])
def product_detail(product_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products WHERE id=%s", (product_id,))
    product = cursor.fetchone()
    cursor.close()
    db.close()

    if request.method == 'POST':
        qty = int(request.form.get('quantity', 1))
        cart = session.get('cart', {})
        cart[str(product_id)] = cart.get(str(product_id), 0) + qty
        session['cart'] = cart
        flash('Added to cart')
        return redirect(url_for('cart'))

    return render_template('product_detail.html', product=product)
@app.route('/cart')
def cart():
    cart = session.get('cart', {})
    if not cart:
        return render_template('cart.html', items=[], total=0)

    db = get_db()
    cursor = db.cursor(dictionary=True)
    product_ids = tuple(int(pid) for pid in cart.keys())
    format_strings = ','.join(['%s'] * len(product_ids))
    cursor.execute(f"SELECT * FROM products WHERE id IN ({format_strings})", product_ids)
    products = cursor.fetchall()
    cursor.close()
    db.close()

    items = []
    total = 0
    for p in products:
        qty = cart.get(str(p['id']), 0)
        line_total = qty * float(p['price'])
        total += line_total
        items.append({"product": p, "quantity": qty, "line_total": line_total})

    return render_template('cart.html', items=items, total=total)
from functools import wraps

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to continue.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart = session.get('cart', {})
    if not cart:
        flash('Your cart is empty.')
        return redirect(url_for('cart'))

    if request.method == 'POST':
        address = request.form.get('address')
        # Calculate total again
        db = get_db()
        cursor = db.cursor(dictionary=True)
        product_ids = tuple(int(pid) for pid in cart.keys())
        format_strings = ','.join(['%s'] * len(product_ids))
        cursor.execute(f"SELECT * FROM products WHERE id IN ({format_strings})", product_ids)
        products = cursor.fetchall()

        total = 0
        for p in products:
            qty = cart.get(str(p['id']), 0)
            total += qty * float(p['price'])

        # Insert order
        cursor = db.cursor()
        cursor.execute("INSERT INTO orders (user_id, total) VALUES (%s, %s)",
                       (session['user_id'], total))
        order_id = cursor.lastrowid

        for p in products:
            qty = cart.get(str(p['id']), 0)
            cursor.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (%s,%s,%s,%s)",
                (order_id, p['id'], qty, p['price'])
            )

        db.commit()
        cursor.close()
        db.close()

        session['cart'] = {}
        return redirect(url_for('order_confirmation', order_id=order_id))

    return render_template('checkout.html')
@app.route('/order/<int:order_id>/confirmation')
@login_required
def order_confirmation(order_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM orders WHERE id=%s AND user_id=%s",
                   (order_id, session['user_id']))
    order = cursor.fetchone()
    cursor.execute("SELECT oi.*, p.name FROM order_items oi JOIN products p ON oi.product_id=p.id WHERE order_id=%s",
                   (order_id,))
    items = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('order_confirmation.html', order=order, items=items)
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        password_hash = generate_password_hash(password)

        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (%s,%s,%s)",
                (name, email, password_hash)
            )
            db.commit()
            flash('Registration successful. Please log in.')
            return redirect(url_for('login'))
        except:
            db.rollback()
            flash('Email already exists.')
        finally:
            cursor.close()
            db.close()

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            flash('Logged in successfully.')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials.')

    return render_template('login.html')



@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.')
    return redirect(url_for('home'))
@app.route('/profile')
@login_required
def profile():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id=%s", (session['user_id'],))
    user = cursor.fetchone()
    cursor.execute("SELECT * FROM orders WHERE user_id=%s ORDER BY created_at DESC",
                   (session['user_id'],))
    orders = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('profile.html', user=user, orders=orders)

def is_admin():
    return session.get('user_email') == 'admin@example.com'

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if not is_admin():
        flash('Access denied.')
        return redirect(url_for('home'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        category = request.form['category']
        image_url = request.form['image_url']
        desc = request.form['description']
        cursor2 = db.cursor()
        cursor2.execute(
            "INSERT INTO products (name, description, price, image_url, category, stock) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (name, desc, price, image_url, category, 10)
        )
        db.commit()
        cursor2.close()
        flash('Product added.')

    cursor.execute("SELECT * FROM products ORDER BY id DESC")
    products = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('admin.html', products=products)

if __name__ == '__main__':
    app.run(debug=True)

# Imports
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import os, json, uuid
import bcrypt
import datetime
from functools import wraps
from collections import defaultdict

#App Configuration
app = Flask(__name__)
app.config['SECRET_KEY'] = uuid.uuid4().hex

data_dir = 'data'
users_file = os.path.join(data_dir, 'users.json')
transaction_date_format = '%Y-%m-%d'
datetime_storage_format = '%Y-%m-%d %H:%M:%S'

# Authentication decorator
def login_required(f):
    """Ensures user is logged in before accessing protected routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# User data management
def load_users():
    if not os.path.exists(users_file):
        return {}
    try:
        with open(users_file, 'r') as f:
            users_list = json.load(f)
            users_dict = {user['username']: user for user in users_list}
            return users_dict
    except json.JSONDecodeError:
        return {}

def save_users(users_dict):
    os.makedirs(data_dir, exist_ok=True)
    users_list = list(users_dict.values())
    with open(users_file, 'w') as f:
        json.dump(users_list, f, indent=4)

#Password Management
def hash_password(password):
    password_bytes = password.encode('utf-8')
    hashed_bytes = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed_bytes.decode('utf-8')

def check_password(stored_hash_str, provided_password):
    password_bytes = provided_password.encode('utf-8')
    stored_hash_bytes = stored_hash_str.encode('utf-8')
    return bcrypt.checkpw(password_bytes, stored_hash_bytes)

#Transaction Data
def get_user_transactions_path(user_id):
    return os.path.join(data_dir, f"{user_id}_transactions.json")

def load_transactions(user_id):
    filepath = get_user_transactions_path(user_id)
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def save_transactions(user_id, transactions):
    os.makedirs(data_dir, exist_ok=True)
    filepath = get_user_transactions_path(user_id)
    try:
        with open(filepath, 'w') as f:
            json.dump(transactions, f, indent=4)
    except IOError as e:
        app.logger.error(f"Error saving transactions file for user {user_id}: {e}")

#Transaction Analysis
def calculate_summary(transactions):
    summary = {'total_income': 0.0, 'total_expense': 0.0, 'balance': 0.0}
    for t in transactions:
        amount = t.get('amount', 0.0)
        if t.get('type') == 'income':
            summary['total_income'] += amount
        elif t.get('type') == 'expense':
            summary['total_expense'] += amount
    summary['balance'] = summary['total_income'] - summary['total_expense']
    return summary

def get_categories(transactions):
    categories = set()
    for t in transactions:
        if t.get('type') == 'expense' and t.get('category'):
            categories.add(t['category'])
    return sorted(list(categories))

def calculate_category_summary(transactions):
    category_totals = defaultdict(float)
    for t in transactions:
        if t.get('type') == 'expense' and t.get('category'):
            category_totals[t['category']] += t.get('amount', 0.0)
    return dict(category_totals)

def generate_recommendations(transactions):
    if not transactions:
        return ['No transactions yet. Add some to get insights!']
    summary = calculate_summary(transactions)
    inc = summary['total_income']
    exp = summary['total_expense']
    balance = summary['balance']
    tips = []
    if balance < 0:
        tips.append("WARNING: Your balance is negative!")
    elif inc > 0:
        if exp > 0.9 * inc:
            tips.append(f"High Spending: Expenses ({exp:.2f}) are more than 90% of income ({inc:.2f}). Consider budgeting tighter.")
        elif exp > inc:
            tips.append(f"Overspending: Expenses ({exp:.2f}) exceed income ({inc:.2f}). Aim to reduce costs or increase income.")
    elif exp > 0:
        tips.append("No income recorded, but expenses exist. Ensure income is tracked.")
    category_summary = calculate_category_summary(transactions)
    food_total = category_summary.get('Food', 0.0)
    if food_total > 0 and exp > 0 and food_total > 0.5 * exp:
        tips.append(f"Food Costs: Spending on Food ({food_total:.2f}) is over 50% of total expenses. Explore meal prep or cheaper options.")
    if not tips:
        tips.append("Good balance! Your recorded spending seems manageable relative to income.")
    return tips

# Main navigation and authentication routes
@app.route('/')
def index():
    """Home page - redirect to dashboard if logged in, otherwise login page"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Username and password are required.', 'danger')
            return render_template('register.html')

        users = load_users()
        if username in users:
            flash('Username already exists. Please choose another.', 'warning')
            return render_template('register.html')
        hashed_password_str = hash_password(password)
        user_id = str(uuid.uuid4())
        users[username] = {
            'user_id': user_id,
            'username': username,
            'password_hash': hashed_password_str
        }
        save_users(users)
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        next_url = request.form.get('next') or url_for('dashboard')
        if not username or not password:
            flash('Username and password required.', 'danger')
            return render_template('login.html', next=next_url)
        users = load_users()
        user_data = users.get(username)
        if user_data:
            stored_hash = user_data.get('password_hash')
            if stored_hash and check_password(stored_hash, password):
                session['user_id'] = user_data['user_id']
                session['username'] = user_data['username']
                flash('Login successful!', 'success')
                if next_url and not next_url.startswith(('/', request.host_url)):
                    next_url = url_for('dashboard')
                return redirect(next_url)
            else:
                flash('Invalid username or password.', 'danger')
        else:
            flash('Invalid username or password.', 'danger')
        return render_template('login.html', next=next_url)
    next_url = request.args.get('next')
    return render_template('login.html', next=next_url)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    transactions = load_transactions(user_id)
    try:
        transactions_sorted = sorted(
            transactions,
            key=lambda t: (
                datetime.datetime.strptime(t['date'], transaction_date_format).date(),
                datetime.datetime.strptime(t['added_datetime'], datetime_storage_format)
            ),
            reverse=True
        )
    except ValueError:
        transactions_sorted = transactions
    summary = calculate_summary(transactions)
    categories = get_categories(transactions)
    category_summary = calculate_category_summary(transactions)
    recommendations = generate_recommendations(transactions)
    return render_template(
        'dashboard.html',
        summary=summary,
        categories=categories,
        category_summary=category_summary,
        transactions=transactions_sorted[:20],
        recommendations=recommendations
    )

#Transaction Management
@app.route('/add_transaction', methods=['POST'])
@login_required
def add_transaction():
    user_id = session['user_id']
    trans_type = request.form.get('type')
    amount_str = request.form.get('amount')
    description = request.form.get('description', '').strip()
    category = request.form.get('category', '').strip()
    date_str = request.form.get('date', '').strip()
    if not trans_type or trans_type not in ['income', 'expense']:
        flash('Invalid transaction type selected.', 'danger')
        return redirect(url_for('dashboard'))
    try:
        amount = round(float(amount_str), 2)
        if amount <= 0:
            raise ValueError("Amount must be positive")
    except (ValueError, TypeError):
        flash('Invalid amount entered. Please enter a positive number.', 'danger')
        return redirect(url_for('dashboard'))
    if trans_type == 'expense' and not category:
        category = 'General'
        flash('Expense category defaulted to "General".', 'info')
    try:
        if date_str:
            transaction_date = datetime.datetime.strptime(date_str, transaction_date_format).strftime(transaction_date_format)
        else:
            transaction_date = datetime.datetime.now().strftime(transaction_date_format)
    except ValueError:
        flash('Invalid date format.', 'danger')
        return redirect(url_for('dashboard'))
    transactions = load_transactions(user_id)
    new_transaction = {
        'transaction_id': str(uuid.uuid4()),
        'user_id': user_id,
        'type': trans_type,
        'amount': amount,
        'category': category,
        'description': description,
        'date': transaction_date,
        'added_datetime': datetime.datetime.now().strftime(datetime_storage_format)
    }
    transactions.append(new_transaction)
    save_transactions(user_id, transactions)
    flash(f'{trans_type.capitalize()} of {amount:.2f} added successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/edit_transaction/<transaction_id>', methods=['GET', 'POST'])
@login_required
def edit_transaction(transaction_id):
    user_id = session['user_id']
    transactions = load_transactions(user_id)
    transaction_to_edit = None
    transaction_index = -1
    for i, t in enumerate(transactions):
        if t.get('transaction_id') == transaction_id:
            transaction_to_edit = t
            transaction_index = i
            break
    if not transaction_to_edit:
        flash('Transaction not found.', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        trans_type = request.form.get('type')
        amount_str = request.form.get('amount')
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()
        date_str = request.form.get('date', '').strip()
        error = False
        if not trans_type or trans_type not in ['income', 'expense']:
            flash('Invalid transaction type selected.', 'danger'); error = True
        try:
            amount = round(float(amount_str), 2)
            if amount <= 0:
                raise ValueError("Amount must be positive")
        except (ValueError, TypeError):
            flash('Invalid amount entered.', 'danger'); error = True
        if trans_type == 'expense' and not category:
            category = 'General'
        try:
            if date_str:
                transaction_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').strftime(transaction_date_format)
            else:
                transaction_date = transaction_to_edit.get('date')
                if not transaction_date:
                    transaction_date = datetime.datetime.now().strftime(transaction_date_format)
        except ValueError:
            flash(f'Invalid date format.' , 'danger'); error = True
        if error:
            try:
                current_date_for_input = datetime.datetime.strptime(transaction_to_edit.get('date',''), transaction_date_format).strftime('%Y-%m-%d')
            except ValueError:
                current_date_for_input = ''
            transaction_to_edit['date_for_input'] = current_date_for_input
            return render_template('edit_transaction.html', transaction=transaction_to_edit)
        transactions[transaction_index]['type'] = trans_type
        transactions[transaction_index]['amount'] = amount
        transactions[transaction_index]['description'] = description
        transactions[transaction_index]['category'] = category
        transactions[transaction_index]['date'] = transaction_date
        save_transactions(user_id, transactions)
        flash('Transaction updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    else:
        try:
            stored_date_str = transaction_to_edit.get('date','')
            date_for_input = datetime.datetime.strptime(stored_date_str, transaction_date_format).strftime('%Y-%m-%d')
        except ValueError:
            date_for_input = ""
        transaction_to_edit['date_for_input'] = date_for_input
        all_transactions = load_transactions(user_id)
        categories = get_categories(all_transactions)
        return render_template('edit_transaction.html', transaction=transaction_to_edit, categories=categories)

@app.route('/delete_transaction/<transaction_id>', methods=['POST'])
@login_required
def delete_transaction(transaction_id):
    user_id = session['user_id']
    transactions = load_transactions(user_id)
    transaction_to_delete = None
    index_to_delete = -1
    for i, t in enumerate(transactions):
        if t.get('transaction_id') == transaction_id:
            transaction_to_delete = t
            index_to_delete = i
            break
    if transaction_to_delete:
        transactions.pop(index_to_delete)
        save_transactions(user_id, transactions)
        flash(f"Transaction {transaction_to_delete.get('description', 'N/A')} deleted successfully.", 'success')
    else:
        flash('Transaction not found.', 'danger')
    return redirect(url_for('dashboard'))

# Dynamic content
@app.route('/get_chart_data', methods=['GET'])
@login_required
def get_chart_data():
    user_id = session['user_id']
    chart_type = request.args.get('type', 'category')
    mode = request.args.get('mode', 'all_time')
    month = request.args.get('month')
    year = request.args.get('year')
    transactions = load_transactions(user_id)
    if mode == 'month' and month and year:
        transactions = [t for t in transactions if t.get('date', '').startswith(f'{year}-{month}')]
    if chart_type == 'category':
        category_summary = calculate_category_summary(transactions)
        data = {
            'labels': list(category_summary.keys()),
            'datasets': [{
                'data': list(category_summary.values()),
                'backgroundColor': [
                    '#4F46E5', '#10B981', '#F59E0B', '#EF4444', '#3B82F6',
                    '#8B5CF6', '#EC4899', '#06B6D4', '#84CC16', '#6366F1'
                ]
            }]
        }
        return json.dumps(data), 200, {'Content-Type': 'application/json'}
    elif chart_type == 'income_vs_expense':
        if mode == 'month' and month and year:
            days_in_month = [f'{year}-{month}-{str(day).zfill(2)}' for day in range(1, 32)]
            daily_income = {d: 0.0 for d in days_in_month}
            daily_expense = {d: 0.0 for d in days_in_month}
            for t in transactions:
                date = t.get('date', '')
                if date in daily_income:
                    if t.get('type') == 'income':
                        daily_income[date] += t.get('amount', 0)
                    elif t.get('type') == 'expense':
                        daily_expense[date] += t.get('amount', 0)
            all_days = sorted(set([t.get('date') for t in transactions if t.get('date', '').startswith(f'{year}-{month}')]))
            data = {
                'labels': all_days,
                'datasets': [
                    {
                        'label': 'Income',
                        'data': [daily_income[d] for d in all_days],
                        'borderColor': '#10B981',
                        'backgroundColor': 'rgba(16,185,129,0.1)',
                        'tension': 0.1,
                        'fill': False
                    },
                    {
                        'label': 'Expenses',
                        'data': [daily_expense[d] for d in all_days],
                        'borderColor': '#EF4444',
                        'backgroundColor': 'rgba(239,68,68,0.1)',
                        'tension': 0.1,
                        'fill': False
                    }
                ]
            }
            return json.dumps(data), 200, {'Content-Type': 'application/json'}
        else:
            return json.dumps({'labels': [], 'datasets': []}), 200, {'Content-Type': 'application/json'}
    elif chart_type == 'monthly_trend':
        monthly_income = defaultdict(float)
        monthly_expense = defaultdict(float)
        for t in transactions:
            try:
                date = datetime.datetime.strptime(t.get('date', ''), transaction_date_format)
                month_key = date.strftime('%Y-%m')
                if t.get('type') == 'income':
                    monthly_income[month_key] += t.get('amount', 0)
                elif t.get('type') == 'expense':
                    monthly_expense[month_key] += t.get('amount', 0)
            except (ValueError, TypeError):
                continue
        all_months = sorted(set(list(monthly_income.keys()) + list(monthly_expense.keys())))
        data = {
            'labels': all_months,
            'datasets': [
                {
                    'label': 'Income',
                    'data': [monthly_income[m] for m in all_months],
                    'borderColor': '#10B981',
                    'backgroundColor': 'rgba(16,185,129,0.1)',
                    'type': 'line',
                    'tension': 0.1,
                    'fill': False
                },
                {
                    'label': 'Expenses',
                    'data': [monthly_expense[m] for m in all_months],
                    'borderColor': '#EF4444',
                    'backgroundColor': 'rgba(239,68,68,0.1)',
                    'type': 'bar',
                    'tension': 0.1,
                    'fill': False
                }
            ]
        }
        return json.dumps(data), 200, {'Content-Type': 'application/json'}
    return json.dumps({}), 200, {'Content-Type': 'application/json'}

@app.route('/get_summary')
@login_required
def get_summary():
    user_id = session['user_id']
    mode = request.args.get('mode', 'all_time')
    month = request.args.get('month')
    year = request.args.get('year')
    transactions = load_transactions(user_id)
    if mode == 'month' and month and year:
        transactions = [t for t in transactions if t.get('date', '').startswith(f'{year}-{month}')]
    summary = calculate_summary(transactions)
    return jsonify(summary)

@app.route('/get_transactions')
@login_required
def get_transactions():
    user_id = session['user_id']
    mode = request.args.get('mode', 'all_time')
    month = request.args.get('month')
    year = request.args.get('year')
    transactions = load_transactions(user_id)

    if mode == 'month' and month and year:
        transactions = [t for t in transactions if t.get('date', '').startswith(f'{year}-{month}')]

    try:
        transactions_sorted = sorted(
            transactions,
            key=lambda t: (
                datetime.datetime.strptime(t['date'], transaction_date_format).date(),
                datetime.datetime.strptime(t['added_datetime'], datetime_storage_format) # Sort by full datetime for secondary key
            ),
            reverse=True
        )
    except ValueError:
        transactions_sorted = transactions

    return jsonify(transactions_sorted)

@app.route('/get_months_years')
@login_required
def get_months_years():
    user_id = session['user_id']
    transactions = load_transactions(user_id)
    months_years = set()
    for t in transactions:
        date_str = t.get('date', '')
        try:
            dt = datetime.datetime.strptime(date_str, transaction_date_format)
            months_years.add((dt.year, dt.month))
        except Exception:
            continue
    sorted_months_years = sorted(list(months_years), key=lambda x: (x[0], x[1]), reverse=True)
    return jsonify([{'year': y, 'month': str(m).zfill(2)} for y, m in sorted_months_years])

@app.route('/get_transaction/<transaction_id>')
@login_required
def get_transaction(transaction_id):
    user_id = session['user_id']
    transactions = load_transactions(user_id)
    for t in transactions:
        if t.get('transaction_id') == transaction_id:
            try:
                date_for_input = datetime.datetime.strptime(t.get('date',''), transaction_date_format).strftime('%Y-%m-%d')
            except Exception:
                date_for_input = ''
            t['date_for_input'] = date_for_input
            return jsonify(t)
    return jsonify({'error': 'Transaction not found'}), 404

@app.route('/get_recommendations')
@login_required
def get_recommendations():
    user_id = session['user_id']
    mode = request.args.get('mode', 'all_time')
    month = request.args.get('month')
    year = request.args.get('year')
    transactions = load_transactions(user_id)
    if mode == 'month' and month and year:
        transactions = [t for t in transactions if t.get('date', '').startswith(f'{year}-{month}')]
    recommendations = generate_recommendations(transactions)
    return jsonify(recommendations)

#Run app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
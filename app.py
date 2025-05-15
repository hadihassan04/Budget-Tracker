from flask import Flask, render_template, request, redirect, url_for, flash, session
import os, json, uuid
import bcrypt
import datetime
from functools import wraps
from collections import defaultdict

# --- Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_very_secret_and_unguessable_key' # Use a strong key when deploying

data_dir = 'data'
users_file = os.path.join(data_dir, 'users.json')
transaction_date_format = '%Y-%m-%d'
datetime_storage_format = '%Y-%m-%d %H:%M:%S'


def load_users():
    """Loads user data from users.json"""
    if not os.path.exists(users_file):
        return {} 
    try:
        with open(users_file, 'r') as f:
            # Store as {'username': {'user_id': ..., 'password_hash': ...}}
            users_list = json.load(f)
            users_dict = {user['username']: user for user in users_list}
            return users_dict
    except json.JSONDecodeError:
        return {}

def save_users(users_dict):
    os.makedirs(data_dir, exist_ok=True)
    # Convert back to list for saving
    users_list = list(users_dict.values())
    with open(users_file, 'w') as f:
        json.dump(users_list, f, indent=4)

def get_user_transactions_path(user_id):
    return os.path.join(data_dir, f"{user_id}_transactions.json")

def load_transactions(user_id):
    filepath = get_user_transactions_path(user_id)
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return [] # Return empty list if file is corrupt or empty

def save_transactions(user_id, transactions):
    os.makedirs(data_dir, exist_ok=True)
    filepath = get_user_transactions_path(user_id)
    with open(filepath, 'w') as f:
        json.dump(transactions, f, indent=4)

#Password Managment

def hash_password(password):
    password_bytes = password.encode('utf-8')
    hashed_bytes = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed_bytes.decode('utf-8')

def check_password(stored_hash_str, provided_password):
    password_bytes = provided_password.encode('utf-8')
    stored_hash_bytes = stored_hash_str.encode('utf-8')
    return bcrypt.checkpw(password_bytes, stored_hash_bytes)

# --- Transaction Data Helpers ---

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
        print(f"Error saving transactions file for user {user_id}: {e}")


#App Functions

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
    tips = []

    if inc > 0:
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

# --- Flask Decorators ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


# --- Routes ---

@app.route('/')
def index():
    """Redirects to dashboard if logged in, otherwise to login page."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles user registration using bcrypt."""
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

        # Hash password using bcrypt
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
    """Handles user login using bcrypt."""
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
            key=lambda t: datetime.datetime.strptime(t.get('date', datetime.datetime.now().strftime(transaction_date_format)), transaction_date_format),
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
        if amount <= 0: raise ValueError("Amount must be positive")
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
    # --- End Validation ---

    transactions = load_transactions(user_id)
    new_transaction = {
        'transaction_id': str(uuid.uuid4()),
        'user_id': user_id,
        'type': trans_type,
        'amount': amount,
        'category': category if trans_type == 'expense' else None,
        'description': description,
        'date': transaction_date,
        'added_datetime': datetime.datetime.now().strftime(datetime_storage_format)
    }
    transactions.append(new_transaction)
    save_transactions(user_id, transactions)

    flash(f'{trans_type.capitalize()} of {amount:.2f} added successfully!', 'success')
    return redirect(url_for('dashboard'))

# --- Route for Deleting a Transaction ---
@app.route('/delete_transaction/<transaction_id>', methods=['POST'])
@login_required
def delete_transaction(transaction_id):
    user_id = session['user_id']
    transactions = load_transactions(user_id)

    # Find the transaction index by its ID
    transaction_to_delete = None
    index_to_delete = -1
    for i, t in enumerate(transactions):
        if t.get('transaction_id') == transaction_id:
            transaction_to_delete = t # Found it
            index_to_delete = i
            break

    if transaction_to_delete:
        # Remove the transaction from the list
        transactions.pop(index_to_delete)
        save_transactions(user_id, transactions) # Save the updated list
        flash(f"Transaction '{transaction_to_delete.get('description', 'N/A')}' deleted successfully.", 'success')
    else:
        flash('Transaction not found.', 'danger')

    return redirect(url_for('dashboard'))


# --- Route for Editing a Transaction (GET and POST) ---
@app.route('/edit_transaction/<transaction_id>', methods=['GET', 'POST'])
@login_required
def edit_transaction(transaction_id):
    user_id = session['user_id']
    transactions = load_transactions(user_id)

    # Find the transaction to edit
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

    # --- Handle POST request (Form Submission) ---
    if request.method == 'POST':
        # Get updated data from form
        trans_type = request.form.get('type')
        amount_str = request.form.get('amount')
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()
        date_str = request.form.get('date', '').strip()

        # --- Validation (Similar to add_transaction) ---
        error = False
        if not trans_type or trans_type not in ['income', 'expense']:
            flash('Invalid transaction type selected.', 'danger'); error = True
        try:
            amount = round(float(amount_str), 2)
            if amount <= 0: raise ValueError("Amount must be positive")
        except (ValueError, TypeError):
            flash('Invalid amount entered.', 'danger'); error = True
        if trans_type == 'expense' and not category:
            category = 'General'
        try:
            if date_str:
                transaction_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').strftime(transaction_date_format)
            else:
                 transaction_date = transaction_to_edit.get('date')
                 if not transaction_date: # If missing, default to now
                     transaction_date = datetime.datetime.now().strftime(transaction_date_format)

        except ValueError:
            flash(f'Invalid date format.' , 'danger'); error = True

        if error:
            # If validation fails, re-load edit page with existing data
            try:
                 current_date_for_input = datetime.datetime.strptime(transaction_to_edit.get('date',''), transaction_date_format).strftime('%Y-%m-%d')
            except ValueError:
                 current_date_for_input = ''
            transaction_to_edit['date_for_input'] = current_date_for_input
            return render_template('edit_transaction.html', transaction=transaction_to_edit)
        # --- End Validation ---

        # Update the transaction dictionary
        transactions[transaction_index]['type'] = trans_type
        transactions[transaction_index]['amount'] = amount
        transactions[transaction_index]['description'] = description
        transactions[transaction_index]['category'] = category if trans_type == 'expense' else None
        transactions[transaction_index]['date'] = transaction_date

        save_transactions(user_id, transactions)
        flash('Transaction updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    # --- Handle GET request (Show Edit Form) ---
    else:
        try:
            stored_date_str = transaction_to_edit.get('date','')
            date_for_input = datetime.datetime.strptime(stored_date_str, transaction_date_format).strftime('%Y-%m-%d')
        except ValueError:
             date_for_input = "" # Handle case where stored date is invalid or missing

        # Add the formatted date to the dictionary being passed to the template
        transaction_to_edit['date_for_input'] = date_for_input

        all_transactions = load_transactions(user_id)
        categories = get_categories(all_transactions)

        return render_template('edit_transaction.html', transaction=transaction_to_edit, categories=categories)

# --- Route for Chart Data ---
@app.route('/get_chart_data', methods=['GET'])
@login_required
def get_chart_data():
    user_id = session['user_id']
    chart_type = request.args.get('type', 'category')
    
    transactions = load_transactions(user_id)
    
    if chart_type == 'category':
        # Prepare data for category pie chart
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
        # Prepare data for income vs expense bar chart
        summary = calculate_summary(transactions)
        data = {
            'labels': ['Income', 'Expenses'],
            'datasets': [{
                'data': [summary['total_income'], summary['total_expense']],
                'backgroundColor': ['#10B981', '#EF4444']
            }]
        }
        return json.dumps(data), 200, {'Content-Type': 'application/json'}
        
    elif chart_type == 'monthly_trend':
        # Prepare data for monthly spending trends line chart
        # Group transactions by month
        monthly_spending = defaultdict(float)
        categories_by_month = defaultdict(lambda: defaultdict(float))
        
        for transaction in transactions:
            try:
                if transaction.get('type') == 'expense':
                    date = datetime.datetime.strptime(transaction.get('date', ''), transaction_date_format)
                    month_key = date.strftime('%Y-%m')
                    amount = transaction.get('amount', 0)
                    category = transaction.get('category', 'Other')
                    
                    monthly_spending[month_key] += amount
                    categories_by_month[month_key][category] += amount
            except (ValueError, TypeError):
                continue
        
        # Sort months chronologically
        sorted_months = sorted(monthly_spending.keys())
        
        # Get top 5 spending categories over all time
        all_categories = set()
        for month_data in categories_by_month.values():
            all_categories.update(month_data.keys())
        
        category_totals = defaultdict(float)
        for month, categories in categories_by_month.items():
            for category, amount in categories.items():
                category_totals[category] += amount
        
        top_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        top_category_names = [cat[0] for cat in top_categories]
        
        # Generate dataset for total monthly spending
        datasets = [
            {
                'label': 'Total Spending',
                'data': [monthly_spending[month] for month in sorted_months],
                'borderColor': '#EF4444',
                'backgroundColor': 'rgba(239, 68, 68, 0.1)',
                'borderWidth': 3,
                'tension': 0.1
            }
        ]
        
        # Generate colors for top categories
        category_colors = {
            top_category_names[i]: [
                '#3730A3', '#059669', '#DC2626', '#2563EB', '#D97706'
            ][i % 5] for i in range(len(top_category_names))
        }
        
        # Add datasets for top categories if we have enough data
        if len(sorted_months) > 1:
            for category in top_category_names:
                datasets.append({
                    'label': category,
                    'data': [categories_by_month[month].get(category, 0) for month in sorted_months],
                    'borderColor': category_colors.get(category, '#9CA3AF'),
                    'backgroundColor': 'rgba(0, 0, 0, 0)',
                    'borderWidth': 2,
                    'borderDash': [],
                    'tension': 0.1
                })
        
        data = {
            'labels': sorted_months,
            'datasets': datasets
        }
        return json.dumps(data), 200, {'Content-Type': 'application/json'}
    
    return json.dumps({}), 200, {'Content-Type': 'application/json'}


if __name__ == '__main__':
    # Debug=True (auto-reloads)
    app.run(debug=True)
# Budget Buddy

A simple personal budget tracker web application built with Flask. Users can register, log in, and track their income and expenses securely. The app provides summaries, category breakdowns, and spending recommendations.

## Features
- User registration and login (with bcrypt password hashing)
- Add, view, and categorize income and expenses
- Dashboard with summaries and recommendations
- Data stored in JSON files per user

## Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd budget_buddy
   ```

2. **Create a virtual environment (recommended)**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install flask bcrypt
   ```

4. **Run the app**
   ```bash
   python app.py
   ```
   The app will be available at [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Project Structure
- `app.py` - Main Flask application
- `data/` - Stores user and transaction data (auto-created)
- `templates/` - HTML templates
- `.gitignore` - Files and folders to ignore in git

## Notes
- Do **not** commit sensitive data or your `.env` file.
- For production, set a strong `SECRET_KEY` in your config.

## License
MIT License 
# FinSight

FinSight is an AI-powered personal finance and expense tracker built with Django. It goes beyond basic expense logging — it uses machine learning to auto-categorize your expenses, forecasts your future spending based on historical patterns, tracks investments and savings goals, and generates PDF reports of your financial activity.

## Features

- **Expense & Income Tracking**: Log expenses and income with category-wise breakdowns and a personalized dashboard.

- **ML-Based Auto-Categorization**: A TF-IDF + Random Forest classifier automatically predicts the category of an expense based on its description, so you don't have to categorize everything manually.

- **Expense Forecasting**: Predicts upcoming spending based on your historical spending patterns.

- **Savings Goals**: Set savings goals and track progress, including how much you need to save daily to hit your target.

- **Investment Portfolio Tracking**: Track investments across Stocks, Mutual Funds, Gold, Crypto, REITs, ETFs, and more.

- **Recurring Expenses**: Automate tracking of recurring expenses with due-date reminders.

- **PDF Report Generation**: Generate downloadable PDF summaries of your spending and financial activity.

- **Smart Budget Alerts**: Set daily, weekly, monthly, or yearly budget limits and get notified as you approach them.

- **Secure Authentication**: User accounts with secure login and personalized dashboards.

- **Custom Dark UI**: A dark-themed interface with glassmorphism styling and Chart.js-powered visualizations.

## Tech Stack

- **Backend**: Django, Python
- **Machine Learning**: scikit-learn (TF-IDF, Random Forest)
- **Frontend**: HTML, CSS (custom dark theme), Chart.js
- **Database**: SQLite (development)
- **API**: Django REST Framework

## Project Structure

The project is organized into several Django apps, each responsible for a distinct feature area:

- `expenses` — core expense logging and management
- `authentication` — user login/signup
- `userincome` — income tracking
- `userpreferences` — user-specific settings
- `userprofile` — user profile management
- `expense_forecast` — ML-based expense forecasting
- `goals` — savings goals tracking
- `investments` — investment portfolio tracking
- `savings` — savings management
- `report_generation` — PDF report generation
- `api` — REST API endpoints (Django REST Framework)

## Setup

To run this application locally, follow these steps:

1. Clone the repository to your local machine:

   ```bash
   git clone https://github.com/abhishekparihar13/finsight.git
   cd finsight
   ```

2. Create a virtual environment (optional but recommended):

   ```bash
   python -m venv venv
   ```

3. Activate the virtual environment:

   - **Windows**:

     ```bash
     venv\Scripts\activate
     ```

   - **macOS and Linux**:

     ```bash
     source venv/bin/activate
     ```

4. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Apply database migrations:

   ```bash
   python manage.py migrate
   ```

6. Create a superuser account to access the admin panel:

   ```bash
   python manage.py createsuperuser
   ```

7. Start the development server:

   ```bash
   python manage.py runserver
   ```

8. Open your web browser and go to `http://localhost:8000` to access the application.

## Usage

1. Create a new account or log in using your superuser account.

2. Add income and start logging your expenses from the dashboard.

3. Leave the category field empty when adding an expense — the ML model will attempt to auto-categorize it based on the description.

4. Set up savings goals and track your investment portfolio from their respective sections.

5. Check the forecast section to see predicted upcoming expenses based on your spending history.

6. Generate a PDF report of your spending activity from the reports section.

7. To access the admin panel, go to `http://localhost:8000/admin/` and log in with your superuser credentials.

## Contributing

If you'd like to contribute to this project, please follow these steps:

1. Fork the repository on GitHub.

2. Create a new branch for your feature or bug fix:

   ```bash
   git checkout -b feature-name
   ```

3. Make your changes and commit them:

   ```bash
   git commit -m "Add new feature"
   ```

4. Push your changes to your forked repository:

   ```bash
   git push origin feature-name
   ```

5. Create a pull request on the original repository to propose your changes.

## Contributors

Built by Abhishek Parihar, Abhay Kumar Prajapati, and Ayush Patel.

## Acknowledgments

- Thanks to the Django community for creating such a powerful web framework.
- The expense auto-categorization and forecasting features are powered by machine learning models built with scikit-learn.

Feel free to customize and enhance this expense tracker according to your needs. Happy budgeting!

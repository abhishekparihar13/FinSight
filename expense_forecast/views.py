
from django.shortcuts import render
import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from django.utils.timezone import now
from expenses.models import Expense
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
import json
import datetime
from datetime import timedelta
import os
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from statsmodels.tsa.stattools import acf
import math
from django.http import JsonResponse
from decimal import Decimal
#Helper functions to convert float to decimal and vice versa
def to_decimal(value):
    if value is None:
        return Decimal("0")
    return Decimal(str(value))

def to_float(value):
    if value is None:
        return 0.0
    return float(value)

# Fetch the data from the Expense model and create the forecast
@login_required(login_url='/authentication/login')
def forecast(request):
    # Fetch expenses for the last 90 days for the current user
    end_date = now().date()
    start_date = end_date - timedelta(days=90)
    expenses = Expense.objects.filter(owner=request.user, date__gte=start_date, date__lte=end_date).exclude(category__icontains='Investment').order_by('date')

    # Check if there are enough expenses (at least 10 entries)
    if len(expenses) < 10:
        messages.error(request, "Not enough recent expenses to make a reliable forecast. Please add more expenses over time.")
        return render(request, 'expense_forecast/index.html')

    # Create a DataFrame
    data = pd.DataFrame({
        'Date': [expense.date for expense in expenses],
        'Expenses': [float(expense.amount) for expense in expenses],
        'Category': [expense.category for expense in expenses]
    })
    
    # Convert 'Date' to pandas datetime
    data['Date'] = pd.to_datetime(data['Date'])
    
    # ---------------------------------------------------------
    # 1. Overall Forecast Processing
    # ---------------------------------------------------------
    # Group by Date and sum the expenses to get daily totals
    daily_data = data.groupby('Date')['Expenses'].sum()
    
    # Resample to daily frequency and fill missing days with 0
    # This guarantees a monotonic index with frequency 'D'
    daily_data = daily_data.resample('D').sum().fillna(0)

    # If all 0, we can't really forecast well
    if daily_data.sum() == 0:
        messages.error(request, "Total expenses are zero. Cannot forecast.")
        return render(request, 'expense_forecast/index.html')

    forecast_steps = 7
    next_day = end_date + timedelta(days=1)
    forecast_index = pd.date_range(start=next_day, periods=forecast_steps, freq='D')

    try:
        # Fit ARIMA model (1, 1, 1) is generally stable for daily totals
        model = ARIMA(daily_data, order=(1, 1, 1))
        model_fit = model.fit()
        
        # Predict the future expenses
        forecast_res = model_fit.get_forecast(steps=forecast_steps)
        forecast_mean = forecast_res.predicted_mean
        conf_int = forecast_res.conf_int()
        
        # Clip negative forecasts to 0
        forecast_mean = forecast_mean.clip(lower=0)
        conf_lower = conf_int.iloc[:, 0].clip(lower=0)
        conf_upper = conf_int.iloc[:, 1].clip(lower=0)
        
    except Exception as e:
        # Fallback to simple moving average if ARIMA fails completely
        print(f"ARIMA training failed: {e}")
        avg_daily = daily_data.mean()
        forecast_mean = pd.Series([avg_daily] * forecast_steps, index=forecast_index)
        conf_lower = forecast_mean * 0.8
        conf_upper = forecast_mean * 1.2

    # ---------------------------------------------------------
    # 2. Category-wise Forecast Processing
    # ---------------------------------------------------------
    categories = data['Category'].unique()
    category_forecasts = {}
    
    total_historic_expenses = to_decimal(data['Expenses'].sum())
    total_forecasted_expenses = to_decimal(forecast_mean.sum())
    
    for cat in categories:
        cat_data = data[data['Category'] == cat]
        cat_total = to_decimal(cat_data['Expenses'].sum())
        
        # Distribute the total forecasted amount proportionally based on historical category spending
        if total_historic_expenses > 0:
            proportion = cat_total / total_historic_expenses
            predicted_cat_total = total_forecasted_expenses * proportion
            category_forecasts[cat] = predicted_cat_total
        else:
            category_forecasts[cat] = 0

    # Sort categories by forecasted amount
    category_forecasts = dict(sorted(category_forecasts.items(), key=lambda item: item[1], reverse=True))

    # Calculate Summaries
    highest_category = list(category_forecasts.keys())[0] if category_forecasts and list(category_forecasts.values())[0] > 0 else "N/A"
    
    # Average daily past 30 days
    past_30_days_data = daily_data.tail(30)
    avg_daily_past = past_30_days_data.mean() if not past_30_days_data.empty else 0
    avg_daily_predicted = total_forecasted_expenses / forecast_steps

    # Spending Trend (Past 7 Days vs Next 7 Days)
    past_7_days_total = Decimal(str(daily_data.tail(7).sum()))
    if past_7_days_total > 0:
        trend_percentage = ((total_forecasted_expenses - past_7_days_total) / past_7_days_total) * 100
    else:
        trend_percentage = 0

    # ---------------------------------------------------------
    # 3. Generate AI Insights
    # ---------------------------------------------------------
    insights = []
    
    # Trend Insight
    if trend_percentage > 5:
        insights.append(f"Your spending is expected to increase by {trend_percentage:.1f}% next week compared to last week.")
    elif trend_percentage < -5:
        insights.append(f"Great job! Your spending is projected to decrease by {abs(trend_percentage):.1f}% next week.")
    else:
        insights.append("Your spending trend looks stable for the upcoming week.")
        
    # Category Insight
    if highest_category != "N/A":
        insights.append(f"Watch out for '{highest_category}' expenses; it's predicted to be your highest spending category.")
        
    # Budget Insight (using average past daily spend as a baseline)
    if avg_daily_predicted > avg_daily_past * 1.2:
        insights.append("You may exceed your typical monthly budget if you maintain this predicted spending rate.")
    elif avg_daily_predicted < avg_daily_past * 0.8:
        insights.append("You are currently spending significantly less than your historical average.")

    # ---------------------------------------------------------
    # 4. Prepare data for Chart.js
    # ---------------------------------------------------------
    import math
    def sanitize_data(lst):
        # Bulletproof sanitization to handle any strange types (e.g., nested lists) and prevent NaNs
        result = []
        for x in lst:
            try:
                # If it's some sort of list/array, extract the first numerical value
                if isinstance(x, (list, tuple, np.ndarray, pd.Series)):
                    x = x[0] if len(x) > 0 else None
                
                # Check for None or pandas/math NaN safely
                if x is None or pd.isna(x):
                    result.append(None)
                else:
                    val = float(x)
                    if math.isnan(val):
                        result.append(None)
                    else:
                        result.append(val)
            except Exception:
                result.append(None)
        return result

    # Use only the last 30 days of historic data for a cleaner chart visualization
    chart_historic_data = daily_data.tail(30)
    chart_historic_dates = chart_historic_data.index.strftime('%Y-%m-%d').tolist()
    chart_historic_values = sanitize_data(chart_historic_data.tolist())
    
    chart_forecast_dates = forecast_index.strftime('%Y-%m-%d').tolist()
    chart_forecast_values = sanitize_data(forecast_mean.tolist())
    
    chart_conf_lower = sanitize_data(conf_lower.tolist())
    chart_conf_upper = sanitize_data(conf_upper.tolist())

    # Create unified labels
    all_chart_labels = chart_historic_dates + chart_forecast_dates
    
    # Pad historic and forecast
    padded_historic = chart_historic_values + [None] * len(chart_forecast_dates)
    padded_forecast = [None] * len(chart_historic_dates) + chart_forecast_values
    
    padded_lower = [None] * len(chart_historic_dates) + chart_conf_lower
    padded_upper = [None] * len(chart_historic_dates) + chart_conf_upper

    # Connect the lines
    if len(chart_historic_values) > 0:
        last_val = chart_historic_values[-1]
        padded_forecast[len(chart_historic_dates)-1] = last_val
        padded_lower[len(chart_historic_dates)-1] = last_val
        padded_upper[len(chart_historic_dates)-1] = last_val

    # Category pie chart data
    cat_labels = list(category_forecasts.keys())
    cat_values = sanitize_data(list(category_forecasts.values()))

    context = {
        'total_forecasted_expenses': float(total_forecasted_expenses) if not pd.isna(total_forecasted_expenses) else 0.0,
        'highest_category': highest_category,
        'avg_daily_predicted': float(avg_daily_predicted) if not pd.isna(avg_daily_predicted) else 0.0,
        'trend_percentage': float(trend_percentage) if not pd.isna(trend_percentage) else 0.0,
        'insights': insights,
        
        # Chart JSONs
        'chart_labels': json.dumps(all_chart_labels),
        'historic_expenses': json.dumps(padded_historic),
        'forecast_expenses': json.dumps(padded_forecast),
        'conf_lower': json.dumps(padded_lower),
        'conf_upper': json.dumps(padded_upper),
        
        'cat_labels': json.dumps(cat_labels),
        'cat_values': json.dumps(cat_values),
        'category_forecasts': category_forecasts,
    }



    return render(request, 'expense_forecast/index.html', context)

@login_required(login_url='/authentication/login')
def retrain_model_view(request):
    if request.method == 'POST':
        try:
            from expenses.ml.model_service import retrain_model
            retrain_model()
            return JsonResponse({'status': 'success', 'message': 'Model retrained successfully!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'POST only'}, status=405)

@login_required(login_url='/authentication/login')
def accuracy(request):
    context = {}
    
    # Fetch expenses for the last 90 days for the current user to run ARIMA
    end_date = now().date()
    start_date = end_date - timedelta(days=90)
    expenses = Expense.objects.filter(owner=request.user, date__gte=start_date, date__lte=end_date).exclude(category__icontains='Investment').order_by('date')
    
    if len(expenses) >= 10:
        data = pd.DataFrame({
            'Date': [expense.date for expense in expenses],
            'Expenses': [float(expense.amount) for expense in expenses],
            'Category': [expense.category for expense in expenses]
        })
        data['Date'] = pd.to_datetime(data['Date'])
        daily_data = data.groupby('Date')['Expenses'].sum()
        daily_data = daily_data.resample('D').sum().fillna(0)
        
        try:
            model = ARIMA(daily_data, order=(1, 1, 1))
            model_fit = model.fit()
        except Exception as e:
            model_fit = None
    else:
        daily_data = None
        model_fit = None

    # --- A) RandomForest Categorisation Model Accuracy ---
    try:
        BASE_DIR_ML = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        DATASET_PATH = os.path.join(BASE_DIR_ML, 'expenses', 'dataset.csv')
        MODEL_PATH = os.path.join(BASE_DIR_ML, 'expenses', 'ml', 'model.pkl')
        VECTORIZER_PATH = os.path.join(BASE_DIR_ML, 'expenses', 'ml', 'vectorizer.pkl')

        rf_data = pd.read_csv(DATASET_PATH)
        rf_data = rf_data.dropna(subset=['clean_description', 'category'])
        rf_data = rf_data[rf_data['category'] != 'category']  # drop header row if duplicated

        X_text = rf_data['clean_description']
        y_labels = rf_data['category']

        rf_model = joblib.load(MODEL_PATH)
        rf_vectorizer = joblib.load(VECTORIZER_PATH)

        X_vec = rf_vectorizer.transform(X_text)

        X_train, X_test, y_train, y_test = train_test_split(
            X_vec, y_labels, test_size=0.2, random_state=42, stratify=None
        )

        y_pred = rf_model.predict(X_test)

        rf_accuracy = round(accuracy_score(y_test, y_pred) * 100, 2)

        report_dict = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
        # Build per-category metrics list sorted by support descending
        rf_per_category = []
        for cat, metrics in report_dict.items():
            if cat in ('accuracy', 'macro avg', 'weighted avg'):
                continue
            rf_per_category.append({
                'category': cat,
                'precision': round(metrics.get('precision', 0) * 100, 1),
                'recall': round(metrics.get('recall', 0) * 100, 1),
                'f1': round(metrics.get('f1-score', 0) * 100, 1),
                'support': int(metrics.get('support', 0)),
            })
        rf_per_category.sort(key=lambda x: x['support'], reverse=True)

        cm = confusion_matrix(y_test, y_pred, labels=list(y_test.unique()))
        cm_labels = list(y_test.unique())
        cm_list = cm.tolist()

        rf_total_samples = len(rf_data)
        rf_test_samples = len(y_test)
        rf_num_categories = len(cm_labels)
        rf_weighted_f1 = round(report_dict['weighted avg']['f1-score'] * 100, 2)
        rf_macro_f1 = round(report_dict['macro avg']['f1-score'] * 100, 2)

        rf_error = None
    except Exception as e:
        rf_accuracy = None
        rf_per_category = []
        cm_list = []
        cm_labels = []
        rf_total_samples = 0
        rf_test_samples = 0
        rf_num_categories = 0
        rf_weighted_f1 = 0
        rf_macro_f1 = 0
        rf_error = str(e)

    # --- B) ARIMA Forecast Model Quality Metrics ---
    try:
        if model_fit is None:
            raise Exception("ARIMA model could not be fitted due to insufficient data.")
        
        # Use the already-fitted model_fit from above (ARIMA)
        arima_aic = round(model_fit.aic, 2)
        arima_bic = round(model_fit.bic, 2)

        # In-sample residuals
        residuals = model_fit.resid
        mae = round(float(np.mean(np.abs(residuals))), 2)
        rmse = round(float(np.sqrt(np.mean(residuals**2))), 2)

        # Mean absolute percentage error on last 14 days (hold-out simulation)
        if daily_data is not None and len(daily_data) >= 21:
            train_arima = daily_data.iloc[:-7]
            test_arima = daily_data.iloc[-7:]
            holdout_model = ARIMA(train_arima, order=(1, 1, 1))
            holdout_fit = holdout_model.fit()
            holdout_forecast = holdout_fit.get_forecast(steps=7).predicted_mean.clip(lower=0)
            actual_vals = np.array(test_arima.values).flatten()
            pred_vals = np.array(holdout_forecast.values).flatten()
            nonzero_mask = actual_vals != 0
            if nonzero_mask.sum() > 0:
                mape = round(float(np.mean(np.abs((actual_vals[nonzero_mask] - pred_vals[nonzero_mask]) / actual_vals[nonzero_mask])) * 100), 2)
            else:
                mape = None
            arima_accuracy_pct = round(max(0, 100 - mape), 2) if mape is not None else None
        else:
            mape = None
            arima_accuracy_pct = None

        # Residual autocorrelation check (good model = low autocorrelation at lag 1)
        acf_vals = acf(residuals.dropna(), nlags=5, fft=False)
        arima_resid_acf1 = round(float(acf_vals[1]), 4)

        # Training data points
        arima_training_days = int(len(daily_data)) if daily_data is not None else 0
        arima_order = '(1, 1, 1)'
        arima_error = None

    except Exception as e:
        arima_aic = None
        arima_bic = None
        mae = None
        rmse = None
        mape = None
        arima_accuracy_pct = None
        arima_resid_acf1 = None
        arima_training_days = 0
        arima_order = '(1, 1, 1)'
        arima_error = str(e)

    context.update({
        # RF Model
        'rf_accuracy': rf_accuracy,
        'rf_per_category': rf_per_category,
        'rf_per_category_json': json.dumps(rf_per_category),
        'cm_list': json.dumps(cm_list),
        'cm_labels': json.dumps(cm_labels),
        'rf_total_samples': rf_total_samples,
        'rf_test_samples': rf_test_samples,
        'rf_num_categories': rf_num_categories,
        'rf_weighted_f1': rf_weighted_f1,
        'rf_macro_f1': rf_macro_f1,
        'rf_error': rf_error,
        # ARIMA Model
        'arima_aic': arima_aic,
        'arima_bic': arima_bic,
        'arima_mae': mae,
        'arima_rmse': rmse,
        'arima_mape': mape,
        'arima_accuracy_pct': arima_accuracy_pct,
        'arima_resid_acf1': arima_resid_acf1,
        'arima_training_days': arima_training_days,
        'arima_order': arima_order,
        'arima_error': arima_error,
    })

    return render(request, 'expense_forecast/accuracy.html', context)

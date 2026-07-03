from django.shortcuts import render, redirect,HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from .models import Category, Expense
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Sum
from django.core.paginator import Paginator
import json
from django.http import JsonResponse
import datetime
import requests
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from django.contrib.sessions.models import Session
from datetime import date
import requests
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import nltk
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
import datetime
from .models import ExpenseLimit, Notification
from django.core.mail import send_mail
from django.conf import settings
from expenses.services.dataset_service import update_dataset, bulk_update_dataset
from expenses.ml.model_service import predict_category
import os
import google.generativeai as genai
from PIL import Image
import io
from decimal import Decimal
from savings.models import SpendingControl
#Helper functions to convert float to decimal and vice versa
def to_decimal(value):
    if value is None:
        return Decimal("0")
    return Decimal(str(value))

def to_float(value):
    if value is None:
        return 0.0
    return float(value)

def check_expense_limits(user, request):
    limit = ExpenseLimit.objects.filter(owner=user).first()
    if not limit: return

    today = datetime.date.today()
    one_week_ago = today - datetime.timedelta(days=7)
    
    daily_expense = to_decimal(Expense.objects.filter(owner=user, date=today).exclude(category__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or 0)
    weekly_expense = to_decimal(Expense.objects.filter(owner=user, date__range=[one_week_ago, today]).exclude(category__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or 0)
    monthly_expense = to_decimal(Expense.objects.filter(owner=user, date__month=today.month, date__year=today.year).exclude(category__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or 0)
    yearly_expense = to_decimal(Expense.objects.filter(owner=user, date__year=today.year).exclude(category__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or 0)

    thresholds = [90, 50]
    
    periods = [
        ('daily', daily_expense, limit.daily_expense_limit),
        ('weekly', weekly_expense, limit.weekly_expense_limit),
        ('monthly', monthly_expense, limit.monthly_expense_limit),
        ('yearly', yearly_expense, limit.yearly_expense_limit)
    ]
    
    for period_name, spent, max_limit in periods:
        if max_limit > 0:
            pct = (spent / max_limit) * 100
            for t in thresholds:
                if pct >= t:
                    if not Notification.objects.filter(user=user, period=period_name, threshold=t, date_triggered=today).exists():
                        msg = f"You have reached {t}% of your {period_name} expense limit!"
                        Notification.objects.create(user=user, message=msg, period=period_name, threshold=t, date_triggered=today)
                        messages.warning(request, msg)
                        messages.warning(request, msg)
                    break

def check_two_tier_guard(user, amount, expense_id_to_exclude=None):
    from userincome.models import UserIncome
    today = datetime.date.today()
    
    total_income = to_decimal(UserIncome.objects.filter(owner=user, date__year=today.year, date__month=today.month).exclude(source__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or 0)
    
    expenses_qs = Expense.objects.filter(owner=user, date__year=today.year, date__month=today.month).exclude(category__icontains='Investment')
    if expense_id_to_exclude:
        expenses_qs = expenses_qs.exclude(id=expense_id_to_exclude)
    total_expenses = to_decimal(expenses_qs.aggregate(Sum('amount'))['amount__sum'] or 0)
    
    total_income_all_time = to_decimal(UserIncome.objects.filter(owner=user).exclude(source__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or 0)
    
    expenses_all_time_qs = Expense.objects.filter(owner=user).exclude(category__icontains='Investment')
    if expense_id_to_exclude:
        expenses_all_time_qs = expenses_all_time_qs.exclude(id=expense_id_to_exclude)
    total_expenses_all_time = to_decimal(expenses_all_time_qs.aggregate(Sum('amount'))['amount__sum'] or 0)
    
    cumulative_savings = total_income_all_time - total_expenses_all_time

    tier_2_blocked = False
    tier_1_warning = False
    drawdown_amount = Decimal('0')

    if amount > cumulative_savings:
        tier_2_blocked = True
    elif (total_expenses + amount) > total_income:
        tier_1_warning = True
        available_this_month = total_income - total_expenses
        if available_this_month > 0:
            drawdown_amount = amount - available_this_month
        else:
            drawdown_amount = amount
            
    return tier_2_blocked, tier_1_warning, drawdown_amount, cumulative_savings

@login_required(login_url='/authentication/login')
def check_limit_preview(request):
    """AJAX endpoint: check if an amount would breach limits before saving."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        amount = Decimal(request.POST.get('amount', '0'))
    except Exception:
        return JsonResponse({'error': 'Invalid amount'}, status=400)
        
    expense_id = request.POST.get('expense_id')

    today = datetime.date.today()
    limit = ExpenseLimit.objects.filter(owner=request.user).first()
    spending_control = SpendingControl.objects.filter(owner=request.user).first()
    allow_overspending = spending_control.allow_overspending if spending_control else True

    tier_2_blocked, tier_1_warning, drawdown_amount, cumulative_savings = check_two_tier_guard(request.user, amount, expense_id)

    breaches = []
    if limit:
        daily_qs = Expense.objects.filter(owner=request.user, date=today).exclude(category__icontains='Investment')
        weekly_qs = Expense.objects.filter(owner=request.user, date__gte=today - datetime.timedelta(days=7)).exclude(category__icontains='Investment')
        monthly_qs = Expense.objects.filter(owner=request.user, date__year=today.year, date__month=today.month).exclude(category__icontains='Investment')
        yearly_qs = Expense.objects.filter(owner=request.user, date__year=today.year).exclude(category__icontains='Investment')
        
        if expense_id:
            daily_qs = daily_qs.exclude(id=expense_id)
            weekly_qs = weekly_qs.exclude(id=expense_id)
            monthly_qs = monthly_qs.exclude(id=expense_id)
            yearly_qs = yearly_qs.exclude(id=expense_id)
            
        daily_total = to_decimal(daily_qs.aggregate(Sum('amount'))['amount__sum'] or 0)
        weekly_total = to_decimal(weekly_qs.aggregate(Sum('amount'))['amount__sum'] or 0)
        monthly_total = to_decimal(monthly_qs.aggregate(Sum('amount'))['amount__sum'] or 0)
        yearly_total = to_decimal(yearly_qs.aggregate(Sum('amount'))['amount__sum'] or 0)

        if limit.daily_expense_limit   > 0 and (daily_total   + amount) > Decimal(str(limit.daily_expense_limit)):
            breaches.append(f"daily (limit ₹{limit.daily_expense_limit:,.0f}, would reach ₹{daily_total + amount:,.0f})")
        if limit.weekly_expense_limit  > 0 and (weekly_total  + amount) > Decimal(str(limit.weekly_expense_limit)):
            breaches.append(f"weekly (limit ₹{limit.weekly_expense_limit:,.0f}, would reach ₹{weekly_total + amount:,.0f})")
        if limit.monthly_expense_limit > 0 and (monthly_total + amount) > Decimal(str(limit.monthly_expense_limit)):
            breaches.append(f"monthly (limit ₹{limit.monthly_expense_limit:,.0f}, would reach ₹{monthly_total + amount:,.0f})")
        if limit.yearly_expense_limit  > 0 and (yearly_total  + amount) > Decimal(str(limit.yearly_expense_limit)):
            breaches.append(f"yearly (limit ₹{limit.yearly_expense_limit:,.0f}, would reach ₹{yearly_total + amount:,.0f})")

    return JsonResponse({
        'breaches': breaches, 
        'allow_overspending': allow_overspending,
        'tier_2_blocked': tier_2_blocked,
        'tier_1_warning': tier_1_warning,
        'drawdown_amount': float(drawdown_amount),
        'cumulative_savings': float(cumulative_savings)
    })


@login_required(login_url='/authentication/login')
def search_expenses(request):
    if request.method == 'POST':
        search_str = json.loads(request.body).get('searchText')
        expenses = Expense.objects.filter(
            amount__istartswith=search_str, owner=request.user) | Expense.objects.filter(
            date__istartswith=search_str, owner=request.user) | Expense.objects.filter(
            description__icontains=search_str, owner=request.user) | Expense.objects.filter(
            category__icontains=search_str, owner=request.user)
        data = expenses.values()
        return JsonResponse(list(data), safe=False)


@login_required(login_url='/authentication/login')
def index(request):
    categories = Expense.objects.filter(owner=request.user).values('category').distinct().order_by('category')
    expenses = Expense.objects.filter(owner=request.user).order_by('-date')

    # Filtering logic
    category = request.GET.get('category')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    amount_min = request.GET.get('amount_min')
    amount_max = request.GET.get('amount_max')
    
    active_filters = False

    if category:
        expenses = expenses.filter(category=category)
        active_filters = True
    if date_from:
        expenses = expenses.filter(date__gte=date_from)
        active_filters = True
    if date_to:
        expenses = expenses.filter(date__lte=date_to)
        active_filters = True
    if amount_min:
        expenses = expenses.filter(amount__gte=amount_min)
        active_filters = True
    if amount_max:
        expenses = expenses.filter(amount__lte=amount_max)
        active_filters = True

    sort_order = request.GET.get('sort')

    if sort_order == 'amount_asc':
        expenses = expenses.order_by('amount')
    elif sort_order == 'amount_desc':
        expenses = expenses.order_by('-amount')
    elif sort_order == 'date_asc':
        expenses = expenses.order_by('date')
    elif sort_order == 'date_desc':
        expenses = expenses.order_by('-date')
    else:
        expenses = expenses.order_by('-date')

    today = date.today()
    current_month_expenses = Expense.objects.filter(owner=request.user, date__year=today.year, date__month=today.month)
    total_this_month = to_decimal(current_month_expenses.aggregate(Sum('amount'))['amount__sum'] or 0)

    highest_category_data = Expense.objects.filter(owner=request.user).exclude(category__icontains='Investment').values('category').annotate(total_amount=Sum('amount')).order_by('-total_amount').first()
    highest_category = highest_category_data['category'] if highest_category_data else "N/A"

    paginator = Paginator(expenses, 5)
    page_number = request.GET.get('page')
    page_obj = Paginator.get_page(paginator, page_number)
    total = page_obj.paginator.num_pages
    
    # Pagination query string builder
    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page']
    filter_query = query_params.urlencode()
    
    context = {
        'categories': categories,
        'expenses': expenses,
        'page_obj': page_obj,
        'total': total,
        'sort_order': sort_order,
        'total_this_month': total_this_month,
        'highest_category': highest_category,
        'filter_category': category,
        'filter_date_from': date_from,
        'filter_date_to': date_to,
        'filter_amount_min': amount_min,
        'filter_amount_max': amount_max,
        'active_filters': active_filters,
        'filter_query': filter_query,
    }
    return render(request, 'expenses/index.html', context)

@login_required(login_url='/authentication/login')
def bulk_delete_expenses(request):
    if request.method == 'POST':
        ids = request.POST.getlist('selected_ids')
        if ids:
            Expense.objects.filter(pk__in=ids, owner=request.user).delete()
            messages.success(request, f'{len(ids)} expense(s) deleted.')
    return redirect('expenses')

daily_expense_amounts = {}

@login_required(login_url='/authentication/login')
def add_expense(request):
    categories = Category.objects.all()
    context = {
        'categories': categories,
        'values': request.POST
    }
    if request.method == 'GET':
        return render(request, 'expenses/add_expense.html', context)

    if request.method == 'POST':
        amount = request.POST['amount']
        date_str = request.POST.get('expense_date')
        
        if not amount:
            messages.error(request, 'Amount is required')
            return render(request, 'expenses/add_expense.html', context)
        description = request.POST['description']
        date = request.POST['expense_date']
        predicted_category = predict_category(description)

        if not description:
            messages.error(request, 'description is required')
            return render(request, 'expenses/add_expense.html', context)
        
        new_category = request.POST.get('category')
        if predicted_category != new_category:
            new_data = {
            'description': description,
            'category': predicted_category,
        }
            predicted_category=new_category

        update_dataset(description, predicted_category)

        try:
            date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            today = datetime.date.today()

            if date > today:
                messages.error(request, 'Date cannot be in the future')
                return render(request, 'expenses/add_expense.html', context)

            new_amount = Decimal(amount)
            today = datetime.date.today()
            limit = ExpenseLimit.objects.filter(owner=request.user).first()
            spending_control = SpendingControl.objects.filter(owner=request.user).first()
            allow_overspending = spending_control.allow_overspending if spending_control else True

            # Evaluate Two-Tier Logic
            tier_2_blocked, tier_1_warning, drawdown_amount, cumulative_savings = check_two_tier_guard(request.user, new_amount)
            force_save = request.POST.get('force_save') == '1'
            
            if 'Investment' not in predicted_category:
                if tier_2_blocked:
                    messages.error(request, f'Transaction Blocked: This expense of ₹{new_amount:,.2f} would exceed your total available funds. You have ₹{cumulative_savings:,.2f} available across income and savings.')
                    return render(request, 'expenses/add_expense.html', context)
                    
                if tier_1_warning:
                    if not allow_overspending:
                        messages.error(request, f'Transaction Blocked: You have exceeded this month\'s income. Overspending is disabled. Enable it in Settings → Limits to draw from savings.')
                        return render(request, 'expenses/add_expense.html', context)
                    elif not force_save:
                        messages.warning(request, f'Warning: This expense exceeds your income for this month. You will be drawing ₹{drawdown_amount:,.2f} from your savings. Available savings: ₹{cumulative_savings:,.2f}. Do you want to continue?')
                        return render(request, 'expenses/add_expense.html', context)

            if limit and 'Investment' not in predicted_category:
                daily_total = to_decimal(Expense.objects.filter(owner=request.user, date=today).exclude(category__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or Decimal('0'))
                weekly_total = to_decimal(Expense.objects.filter(owner=request.user, date__gte=today - datetime.timedelta(days=7)).exclude(category__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or Decimal('0'))
                monthly_total = to_decimal(Expense.objects.filter(owner=request.user, date__year=today.year, date__month=today.month).exclude(category__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or Decimal('0'))
                yearly_total = to_decimal(Expense.objects.filter(owner=request.user, date__year=today.year).exclude(category__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or Decimal('0'))

                breaches = []
                if limit.daily_expense_limit > 0 and (daily_total + new_amount) > Decimal(str(limit.daily_expense_limit)):
                    breaches.append(f"daily (limit ₹{limit.daily_expense_limit:,.0f}, would reach ₹{daily_total + new_amount:,.0f})")
                if limit.weekly_expense_limit > 0 and (weekly_total + new_amount) > Decimal(str(limit.weekly_expense_limit)):
                    breaches.append(f"weekly (limit ₹{limit.weekly_expense_limit:,.0f}, would reach ₹{weekly_total + new_amount:,.0f})")
                if limit.monthly_expense_limit > 0 and (monthly_total + new_amount) > Decimal(str(limit.monthly_expense_limit)):
                    breaches.append(f"monthly (limit ₹{limit.monthly_expense_limit:,.0f}, would reach ₹{monthly_total + new_amount:,.0f})")
                if limit.yearly_expense_limit > 0 and (yearly_total + new_amount) > Decimal(str(limit.yearly_expense_limit)):
                    breaches.append(f"yearly (limit ₹{limit.yearly_expense_limit:,.0f}, would reach ₹{yearly_total + new_amount:,.0f})")

                if breaches:
                    breach_str = ", ".join(breaches)
                    if not allow_overspending and not force_save:
                        # Blocked — JS modal handles display, but if JS is bypassed return error
                        messages.error(request, f'Expense blocked: this would exceed your {breach_str} limit.')
                        return render(request, 'expenses/add_expense.html', context)
                    elif not force_save:
                        # Warning — JS modal not triggered (direct POST), block and show warning
                        messages.warning(request, f'Warning: this expense exceeds your {breach_str} limit.')
                        return render(request, 'expenses/add_expense.html', context)
                    # force_save == '1': user confirmed via modal, proceed to save

            Expense.objects.create(owner=request.user, amount=new_amount, date=date,
                                   category=predicted_category, description=description)
            
            check_expense_limits(request.user, request)
            
            messages.success(request, 'Expense saved successfully')
            return redirect('expenses')
        except ValueError:
            messages.error(request, 'Invalid date format')
            return render(request, 'expenses/add_expense.html', context)


@login_required(login_url='/authentication/login')
def expense_edit(request, id):
    expense = Expense.objects.get(pk=id)
    categories = Category.objects.all()
    context = {
        'expense': expense,
        'values': expense,
        'categories': categories
    }
    if request.method == 'GET':
        return render(request, 'expenses/edit-expense.html', context)
    if request.method == 'POST':
        amount = request.POST['amount']
        date_str = request.POST.get('expense_date')

        if not amount:
            messages.error(request, 'Amount is required')
            return render(request, 'expenses/edit-expense.html', context)
        description = request.POST['description']
        date = request.POST['expense_date']
        category = request.POST['category']

        if not description:
            messages.error(request, 'description is required')
            return render(request, 'expenses/edit-expense.html', context)

        try:
            # Convert the date string to a datetime object and validate the date
            date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            today = datetime.date.today()

            if date > today:
                messages.error(request, 'Date cannot be in the future')
                return render(request, 'expenses/edit-expense.html', context)

            new_amount = Decimal(amount)
            today = datetime.date.today()
            limit = ExpenseLimit.objects.filter(owner=request.user).first()
            spending_control = SpendingControl.objects.filter(owner=request.user).first()
            allow_overspending = spending_control.allow_overspending if spending_control else True

            tier_2_blocked, tier_1_warning, drawdown_amount, cumulative_savings = check_two_tier_guard(request.user, new_amount, expense.id)
            force_save = request.POST.get('force_save') == '1'

            if 'Investment' not in category:
                if tier_2_blocked:
                    messages.error(request, f'Transaction Blocked: This expense of ₹{new_amount:,.2f} would exceed your total available funds. You have ₹{cumulative_savings:,.2f} available across income and savings.')
                    return render(request, 'expenses/edit-expense.html', context)
                    
                if tier_1_warning:
                    if not allow_overspending:
                        messages.error(request, f'Transaction Blocked: You have exceeded this month\'s income. Overspending is disabled. Enable it in Settings → Limits to draw from savings.')
                        return render(request, 'expenses/edit-expense.html', context)
                    elif not force_save:
                        messages.warning(request, f'Warning: This expense exceeds your income for this month. You will be drawing ₹{drawdown_amount:,.2f} from your savings. Available savings: ₹{cumulative_savings:,.2f}. Do you want to continue?')
                        return render(request, 'expenses/edit-expense.html', context)

            if limit and 'Investment' not in category:
                daily_total = to_decimal(Expense.objects.filter(owner=request.user, date=today).exclude(category__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or Decimal('0'))
                weekly_total = to_decimal(Expense.objects.filter(owner=request.user, date__gte=today - datetime.timedelta(days=7)).exclude(category__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or Decimal('0'))
                monthly_total = to_decimal(Expense.objects.filter(owner=request.user, date__year=today.year, date__month=today.month).exclude(category__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or Decimal('0'))
                yearly_total = to_decimal(Expense.objects.filter(owner=request.user, date__year=today.year).exclude(category__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or Decimal('0'))

                breaches = []
                if limit.daily_expense_limit > 0 and (daily_total + new_amount) > Decimal(str(limit.daily_expense_limit)):
                    breaches.append(f"daily (limit ₹{limit.daily_expense_limit:,.0f}, would reach ₹{daily_total + new_amount:,.0f})")
                if limit.weekly_expense_limit > 0 and (weekly_total + new_amount) > Decimal(str(limit.weekly_expense_limit)):
                    breaches.append(f"weekly (limit ₹{limit.weekly_expense_limit:,.0f}, would reach ₹{weekly_total + new_amount:,.0f})")
                if limit.monthly_expense_limit > 0 and (monthly_total + new_amount) > Decimal(str(limit.monthly_expense_limit)):
                    breaches.append(f"monthly (limit ₹{limit.monthly_expense_limit:,.0f}, would reach ₹{monthly_total + new_amount:,.0f})")
                if limit.yearly_expense_limit > 0 and (yearly_total + new_amount) > Decimal(str(limit.yearly_expense_limit)):
                    breaches.append(f"yearly (limit ₹{limit.yearly_expense_limit:,.0f}, would reach ₹{yearly_total + new_amount:,.0f})")

                if breaches:
                    breach_str = ", ".join(breaches)
                    if not allow_overspending:
                        messages.error(request, f'Expense blocked: this would exceed your {breach_str} limit. To allow overspending, enable it in Savings → Spending Control.')
                        return render(request, 'expenses/edit-expense.html', context)
                    else:
                        messages.warning(request, f'Warning: this expense exceeds your {breach_str} limit. The overspent amount will be deducted from your savings.')

            expense.owner = request.user
            expense.amount = new_amount
            expense. date = date
            expense.category = category
            expense.description = description

            expense.save()
            check_expense_limits(request.user, request)
            messages.success(request, 'Expense saved successfully')

            return redirect('expenses')
        except ValueError:
            messages.error(request, 'Invalid date format')
            return render(request, 'expenses/edit_income.html', context)

        # expense.owner = request.user
        # expense.amount = amount
        # expense. date = date
        # expense.category = category
        # expense.description = description

        # expense.save()

        # messages.success(request, 'Expense updated  successfully')

        # return redirect('expenses')

@login_required(login_url='/authentication/login')
def delete_expense(request, id):
    expense = Expense.objects.get(pk=id)
    expense.delete()
    messages.success(request, 'Expense removed')
    return redirect('expenses')

@login_required(login_url='/authentication/login')
def expense_category_summary(request):
    todays_date = datetime.date.today()
    six_months_ago = todays_date-datetime.timedelta(days=30*6)
    expenses = Expense.objects.filter(owner=request.user,
                                      date__gte=six_months_ago, date__lte=todays_date).exclude(category__icontains='Investment')
    finalrep = {}

    def get_category(expense):
        return expense.category
    category_list = list(set(map(get_category, expenses)))

    def get_expense_category_amount(category):
        amount = Decimal('0')
        filtered_by_category = expenses.filter(category=category)

        for item in filtered_by_category:
            amount += item.amount
        return amount

    for x in expenses:
        for y in category_list:
            finalrep[y] = float(get_expense_category_amount(y))

    return JsonResponse({'expense_category_data': finalrep}, safe=False)

@login_required(login_url='/authentication/login')
def stats_view(request):
    user = request.user

    today = datetime.date.today()
    one_week_ago = today - datetime.timedelta(days=7)

    daily_expense = to_decimal(Expense.objects.filter(owner=user, date=today).exclude(category__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or 0)
    weekly_expense = to_decimal(Expense.objects.filter(owner=user, date__range=[one_week_ago, today]).exclude(category__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or 0)
    monthly_expense = to_decimal(Expense.objects.filter(owner=user, date__month=today.month, date__year=today.year).exclude(category__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or 0)
    yearly_expense = to_decimal(Expense.objects.filter(owner=user, date__year=today.year).exclude(category__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or 0)

    context = {
        'daily_expense': daily_expense,
        'weekly_expense': weekly_expense,
        'monthly_expense': monthly_expense,
        'yearly_expense': yearly_expense,
    }
    return render(request, 'expenses/stats.html', context)

    

def set_expense_limit(request):
    if request.method == "POST":
        daily_expense_limit = request.POST.get('daily_expense_limit') or 0
        weekly_expense_limit = request.POST.get('weekly_expense_limit') or 0
        monthly_expense_limit = request.POST.get('monthly_expense_limit') or 0
        yearly_expense_limit = request.POST.get('yearly_expense_limit') or 0
        
        existing_limit = ExpenseLimit.objects.filter(owner=request.user).first()
        
        if existing_limit:
            existing_limit.daily_expense_limit = daily_expense_limit
            existing_limit.weekly_expense_limit = weekly_expense_limit
            existing_limit.monthly_expense_limit = monthly_expense_limit
            existing_limit.yearly_expense_limit = yearly_expense_limit
            existing_limit.save()
        else:
            ExpenseLimit.objects.create(
                owner=request.user, 
                daily_expense_limit=daily_expense_limit,
                weekly_expense_limit=weekly_expense_limit,
                monthly_expense_limit=monthly_expense_limit,
                yearly_expense_limit=yearly_expense_limit
            )
        
        messages.success(request, "Expense Limits Updated Successfully!")
        return HttpResponseRedirect('/preferences/')
    else:
        return HttpResponseRedirect('/preferences/')
    
def get_expense_of_day(user):
    current_date=date.today()
    expenses=Expense.objects.filter(owner=user,date=current_date)
    total_expenses=sum((expense.amount for expense in expenses),Decimal('0'))
    return total_expenses

@login_required(login_url='/authentication/login')
def mark_notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))

def ocr_receipt(request):
    if request.method == 'POST' and request.FILES.get('receipt'):
        try:
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                return JsonResponse({'error': 'Gemini API Key not configured'}, status=500)
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            receipt_file = request.FILES['receipt']
            image = Image.open(receipt_file)
            
            prompt = """
            Extract the following information from this receipt image and return ONLY a valid JSON object. Do not include any markdown formatting like ```json.
            - amount: The total amount paid as a float number (e.g., 25.50)
            - date: The date of the receipt in YYYY-MM-DD format. If no date is found, use null.
            - description: A brief description of the expense based on the store name or items bought (e.g., "Starbucks Coffee", "Grocery from Walmart").
            
            Example output format:
            {
                "amount": 25.50,
                "date": "2023-10-25",
                "description": "Starbucks Coffee"
            }
            """
            response = model.generate_content([prompt, image])
            
            # Clean response text in case the model adds markdown block
            response_text = response.text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            data = json.loads(response_text)
            return JsonResponse(data)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


from .models import RecurringExpense

@login_required(login_url='/authentication/login')
def recurring_expenses(request):
    recurrings = RecurringExpense.objects.filter(owner=request.user).order_by('next_due_date')
    context = {'recurrings': recurrings}
    return render(request, 'expenses/recurring_expenses.html', context)

@login_required(login_url='/authentication/login')
def add_recurring(request):
    categories = Category.objects.all()
    context = {'categories': categories, 'values': request.POST}
    if request.method == 'GET':
        return render(request, 'expenses/add_recurring.html', context)
        
    if request.method == 'POST':
        amount = request.POST['amount']
        description = request.POST['description']
        category = request.POST.get('category')
        frequency = request.POST.get('frequency')
        next_due_date_str = request.POST.get('next_due_date')
        
        if not amount or not description or not frequency or not next_due_date_str:
            messages.error(request, 'All fields are required')
            return render(request, 'expenses/add_recurring.html', context)
            
        try:
            next_due_date = datetime.datetime.strptime(next_due_date_str, '%Y-%m-%d').date()
            RecurringExpense.objects.create(
                owner=request.user,
                amount=amount,
                description=description,
                category=category,
                frequency=frequency,
                next_due_date=next_due_date
            )
            messages.success(request, 'Recurring Expense added successfully')
            return redirect('recurring_expenses')
        except ValueError:
            messages.error(request, 'Invalid date format')
            return render(request, 'expenses/add_recurring.html', context)

@login_required(login_url='/authentication/login')
def edit_recurring(request, id):
    recur = RecurringExpense.objects.get(pk=id, owner=request.user)
    categories = Category.objects.all()
    context = {'recurring': recur, 'values': recur, 'categories': categories}
    
    if request.method == 'GET':
        return render(request, 'expenses/edit_recurring.html', context)
        
    if request.method == 'POST':
        amount = request.POST['amount']
        description = request.POST['description']
        category = request.POST.get('category')
        frequency = request.POST.get('frequency')
        next_due_date_str = request.POST.get('next_due_date')
        
        if not amount or not description or not frequency or not next_due_date_str:
            messages.error(request, 'All fields are required')
            return render(request, 'expenses/edit_recurring.html', context)
            
        try:
            recur.amount = amount
            recur.description = description
            recur.category = category
            recur.frequency = frequency
            recur.next_due_date = datetime.datetime.strptime(next_due_date_str, '%Y-%m-%d').date()
            recur.save()
            messages.success(request, 'Recurring Expense updated successfully')
            return redirect('recurring_expenses')
        except ValueError:
            messages.error(request, 'Invalid date format')
            return render(request, 'expenses/edit_recurring.html', context)

@login_required(login_url='/authentication/login')
def delete_recurring(request, id):
    recur = RecurringExpense.objects.get(pk=id, owner=request.user)
    recur.delete()
    messages.success(request, 'Recurring Expense deleted successfully')
    return redirect('recurring_expenses')


import pandas as pd
from django.utils.dateparse import parse_date
import math
try:
    from expenses.ml.model_service import predict_category
except ImportError:
    # Fallback if ml service is not available
    def predict_category(description):
        return 'Other'

@login_required(login_url='/authentication/login')
def bulk_import_expenses(request):
    if request.method == 'GET':
        return render(request, 'expenses/bulk_import.html')

    if request.method == 'POST':
        if 'file' not in request.FILES:
            messages.error(request, 'Please upload a valid CSV or Excel file.')
            return redirect('bulk-import-expenses')
            
        file = request.FILES['file']
        filename = file.name
        
        try:
            if filename.endswith('.csv'):
                df = pd.read_csv(file)
            elif filename.endswith('.xlsx') or filename.endswith('.xls'):
                df = pd.read_excel(file)
            else:
                messages.error(request, 'Unsupported file format. Please upload .csv or .xlsx')
                return redirect('bulk-import-expenses')
                
            # Normalize column names
            df.columns = [str(col).strip().lower() for col in df.columns]
            
            required_columns = {'date', 'description', 'amount'}
            if not required_columns.issubset(set(df.columns)):
                messages.error(request, f'Missing required columns. Expected at least: date, description, amount. Found: {", ".join(df.columns)}')
                return redirect('bulk-import-expenses')

            imported_count = 0
            skipped_count = 0
            dataset_rows = []

            for index, row in df.iterrows():
                try:
                    # Validate Date
                    raw_date = row['date']
                    if pd.isna(raw_date):
                        skipped_count += 1
                        continue
                    
                    if isinstance(raw_date, str):
                        expense_date = parse_date(raw_date)
                        if not expense_date:
                            # Try to parse with pandas and convert to date
                            expense_date = pd.to_datetime(raw_date).date()
                    else:
                        expense_date = raw_date.date() if hasattr(raw_date, 'date') else pd.to_datetime(raw_date).date()
                    
                    if expense_date > datetime.date.today():
                        skipped_count += 1
                        continue

                    # Validate Description
                    description = str(row['description']).strip()
                    if pd.isna(row['description']) or not description or description == 'nan':
                        skipped_count += 1
                        continue

                    # Validate Amount
                    amount = Decimal(str(row['amount']))
                    if math.isnan(amount) or amount <= 0:
                        skipped_count += 1
                        continue

                    # Category Logic
                    category = str(row.get('category', '')).strip()
                    if pd.isna(row.get('category')) or not category or category == 'nan':
                        category = predict_category(description)

                    # Save Expense
                    Expense.objects.create(
                        owner=request.user,
                        amount=amount,
                        date=expense_date,
                        description=description,
                        category=category
                    )
                    imported_count += 1
                    
                    dataset_rows.append({
                        'description': description,
                        'category': category
                    })
                except Exception as e:
                    skipped_count += 1
                    continue

            if dataset_rows:
                try:
                    bulk_update_dataset(dataset_rows)
                except Exception as e:
                    pass # Ensure bulk import success isn't halted if dataset update fails

            messages.success(request, f'Successfully imported {imported_count} expenses. Skipped {skipped_count} invalid rows.')
            return redirect('expenses')

        except Exception as e:
            messages.error(request, f'Error processing file: {str(e)}')
            return redirect('bulk-import-expenses')

from .models import PendingRecurringExpense

@login_required(login_url='/authentication/login')
def dummy_payment_page(request, id):
    try:
        pending = PendingRecurringExpense.objects.get(pk=id, owner=request.user)
    except PendingRecurringExpense.DoesNotExist:
        messages.error(request, 'Pending expense not found.')
        return redirect('recurring_expenses')
        
    context = {'pending': pending}
    return render(request, 'expenses/dummy_payment.html', context)

@login_required(login_url='/authentication/login')
def pay_pending_expense(request, id):
    if request.method == 'POST':
        try:
            pending = PendingRecurringExpense.objects.get(pk=id, owner=request.user)
            
            new_amount = Decimal(pending.amount)
            today = datetime.date.today()
            limit = ExpenseLimit.objects.filter(owner=request.user).first()
            spending_control = SpendingControl.objects.filter(owner=request.user).first()
            allow_overspending = spending_control.allow_overspending if spending_control else True

            tier_2_blocked, tier_1_warning, drawdown_amount, cumulative_savings = check_two_tier_guard(request.user, new_amount)
            
            force_save = request.POST.get('force_save') == '1'

            if 'Investment' not in pending.category:
                if tier_2_blocked:
                    messages.error(request, f'Transaction Blocked: This expense of ₹{new_amount:,.2f} would exceed your total available funds. You have ₹{cumulative_savings:,.2f} available across income and savings.')
                    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
                    
                if tier_1_warning:
                    if not allow_overspending:
                        messages.error(request, f'Transaction Blocked: You have exceeded this month\'s income. Overspending is disabled. Enable it in Settings → Limits to draw from savings.')
                        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
                    elif not force_save:
                        messages.warning(request, f'Warning: This expense exceeded your income for this month. You drew ₹{drawdown_amount:,.2f} from your savings. Do you want to continue?')
                        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
                    else:
                        messages.warning(request, f'Warning: This expense exceeded your income for this month. You drew ₹{drawdown_amount:,.2f} from your savings.')

            if limit and 'Investment' not in pending.category:
                daily_total = to_decimal(Expense.objects.filter(owner=request.user, date=today).exclude(category__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or Decimal('0'))
                weekly_total = to_decimal(Expense.objects.filter(owner=request.user, date__gte=today - datetime.timedelta(days=7)).exclude(category__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or Decimal('0'))
                monthly_total = to_decimal(Expense.objects.filter(owner=request.user, date__year=today.year, date__month=today.month).exclude(category__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or Decimal('0'))
                yearly_total = to_decimal(Expense.objects.filter(owner=request.user, date__year=today.year).exclude(category__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or Decimal('0'))

                breaches = []
                if limit.daily_expense_limit > 0 and (daily_total + new_amount) > Decimal(str(limit.daily_expense_limit)):
                    breaches.append(f"daily (limit ₹{limit.daily_expense_limit:,.0f}, would reach ₹{daily_total + new_amount:,.0f})")
                if limit.weekly_expense_limit > 0 and (weekly_total + new_amount) > Decimal(str(limit.weekly_expense_limit)):
                    breaches.append(f"weekly (limit ₹{limit.weekly_expense_limit:,.0f}, would reach ₹{weekly_total + new_amount:,.0f})")
                if limit.monthly_expense_limit > 0 and (monthly_total + new_amount) > Decimal(str(limit.monthly_expense_limit)):
                    breaches.append(f"monthly (limit ₹{limit.monthly_expense_limit:,.0f}, would reach ₹{monthly_total + new_amount:,.0f})")
                if limit.yearly_expense_limit > 0 and (yearly_total + new_amount) > Decimal(str(limit.yearly_expense_limit)):
                    breaches.append(f"yearly (limit ₹{limit.yearly_expense_limit:,.0f}, would reach ₹{yearly_total + new_amount:,.0f})")

                if breaches:
                    breach_str = ", ".join(breaches)
                    if not allow_overspending:
                        messages.error(request, f'Expense blocked: this would exceed your {breach_str} limit. To allow overspending, enable it in Savings → Spending Control.')
                        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
                    elif not force_save:
                        messages.warning(request, f'Warning: this expense exceeds your {breach_str} limit. The overspent amount will be deducted from your savings. Do you want to continue?')
                        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
                    else:
                        messages.warning(request, f'Warning: this expense exceeds your {breach_str} limit. The overspent amount will be deducted from your savings.')

            # Create the formal Expense
            Expense.objects.create(
                amount=pending.amount,
                date=datetime.date.today(),
                description=pending.description,
                owner=pending.owner,
                category=pending.category
            )
            
            # Delete pending item
            pending.delete()
            check_expense_limits(request.user, request)
            
            messages.success(request, f'Payment of ₹{pending.amount:,.2f} for {pending.description} was successful and added to your expenses.')
        except PendingRecurringExpense.DoesNotExist:
            messages.error(request, 'Pending expense not found.')
            
    return redirect('recurring_expenses')
from django.shortcuts import render
import os
import json
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from expenses.models import ExpenseLimit, Expense
from django.db.models import Sum
import datetime


from decimal import Decimal

def to_decimal(value):
    return Decimal(str(value or 0))
@login_required(login_url='/authentication/login')
def index(request):
    expense_limit, created = ExpenseLimit.objects.get_or_create(
        owner=request.user,
        defaults={
            'daily_expense_limit': 5000,
            'weekly_expense_limit': 0,
            'monthly_expense_limit': 0,
            'yearly_expense_limit': 0
        }
    )

    today = datetime.date.today()
    one_week_ago = today - datetime.timedelta(days=7)

    daily_expense = to_decimal(Expense.objects.filter(owner=request.user, date=today).aggregate(Sum('amount'))['amount__sum'] or 0)
    weekly_expense = to_decimal(Expense.objects.filter(owner=request.user, date__range=[one_week_ago, today]).aggregate(Sum('amount'))['amount__sum'] or 0)
    monthly_expense = to_decimal(Expense.objects.filter(owner=request.user, date__month=today.month, date__year=today.year).aggregate(Sum('amount'))['amount__sum'] or 0)
    yearly_expense = to_decimal(Expense.objects.filter(owner=request.user, date__year=today.year).aggregate(Sum('amount'))['amount__sum'] or 0)

    daily_pct = min(100, int((daily_expense / expense_limit.daily_expense_limit) * 100)) if expense_limit.daily_expense_limit > 0 else 0
    weekly_pct = min(100, int((weekly_expense / expense_limit.weekly_expense_limit) * 100)) if expense_limit.weekly_expense_limit > 0 else 0
    monthly_pct = min(100, int((monthly_expense / expense_limit.monthly_expense_limit) * 100)) if expense_limit.monthly_expense_limit > 0 else 0
    yearly_pct = min(100, int((yearly_expense / expense_limit.yearly_expense_limit) * 100)) if expense_limit.yearly_expense_limit > 0 else 0

    limits_data = {
        'daily_expense_limit': expense_limit.daily_expense_limit,
        'weekly_expense_limit': expense_limit.weekly_expense_limit,
        'monthly_expense_limit': expense_limit.monthly_expense_limit,
        'yearly_expense_limit': expense_limit.yearly_expense_limit,
        'daily_expense': daily_expense,
        'weekly_expense': weekly_expense,
        'monthly_expense': monthly_expense,
        'yearly_expense': yearly_expense,
        'daily_pct': daily_pct,
        'weekly_pct': weekly_pct,
        'monthly_pct': monthly_pct,
        'yearly_pct': yearly_pct,
    }

    context = {
        **limits_data
    }
    return render(request, 'preferences/index.html', context)

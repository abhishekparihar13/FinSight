import json
import datetime
from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import SpendingControl
from expenses.models import Expense
from userincome.models import UserIncome
from django.db.models import Sum

@login_required(login_url='/authentication/login')
def savings_dashboard(request):
    user = request.user
    spending_control, created = SpendingControl.objects.get_or_create(owner=user)
    
    today = datetime.date.today()
    current_year = today.year
    current_month = today.month

    def get_month_totals(year, month):
        expenses = Expense.objects.filter(owner=user, date__year=year, date__month=month).exclude(category__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or 0
        incomes = UserIncome.objects.filter(owner=user, date__year=year, date__month=month).exclude(source__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or 0
        return float(incomes), float(expenses)

    current_month_income, current_month_expenses = get_month_totals(current_year, current_month)
    monthly_savings = max(0, current_month_income - current_month_expenses)

    # Real deficit this month (positive number means overspent)
    monthly_deficit = max(0.0, current_month_expenses - current_month_income)
    overspent_this_month = monthly_deficit > 0

    if current_month == 1:
        prev_month = 12
        prev_year = current_year - 1
    else:
        prev_month = current_month - 1
        prev_year = current_year
        
    prev_month_income, prev_month_expenses = get_month_totals(prev_year, prev_month)
    prev_monthly_savings = max(0, prev_month_income - prev_month_expenses)

    if prev_monthly_savings > 0:
        monthly_savings_change = ((monthly_savings - prev_monthly_savings) / prev_monthly_savings) * 100
    else:
        monthly_savings_change = None if monthly_savings == 0 else 100.0

    savings_rate = round((monthly_savings / current_month_income) * 100, 1) if current_month_income > 0 else 0.0

    # YTD and Best Month
    ytd_savings = 0
    best_month_savings = 0
    best_month_label = "None"
    
    ytd_overspent = 0.0
    for m in range(1, current_month + 1):
        m_inc, m_exp = get_month_totals(current_year, m)
        m_save = max(0, m_inc - m_exp)
        ytd_savings += m_save
        if m_exp > m_inc:
            ytd_overspent += (m_exp - m_inc)
        if m_save >= best_month_savings and m_save > 0:
            best_month_savings = m_save
            best_month_label = datetime.date(current_year, m, 1).strftime('%b %Y')

    # Effective YTD savings after deducting overspent months
    effective_ytd_savings = max(0.0, ytd_savings - ytd_overspent)

    # Last 6 months chart data
    chart_labels = []
    chart_income = []
    chart_expenses = []
    chart_savings = []
    rate_trend = [] 
    
    for i in range(5, -1, -1):
        m = current_month - i
        y = current_year
        while m <= 0:
            m += 12
            y -= 1
        
        m_inc, m_exp = get_month_totals(y, m)
        m_save = max(0, m_inc - m_exp)
        m_rate = round((m_save / m_inc) * 100, 1) if m_inc > 0 else 0.0
        
        chart_labels.append(datetime.date(y, m, 1).strftime('%b'))
        chart_income.append(m_inc)
        chart_expenses.append(m_exp)
        chart_savings.append(m_save)
        rate_trend.append(m_rate)

    # Tips logic
    tips = []
    
    cat_expenses = Expense.objects.filter(owner=user, date__year=current_year, date__month=current_month)\
        .exclude(category__icontains='Investment')\
        .values('category').annotate(total=Sum('amount')).order_by('-total')
    
    if overspent_this_month:
        tips.insert(0, {
            'icon': 'alert-triangle', 'color': 'danger',
            'title': 'Overspending Detected',
            'body': f'You overspent by ₹{monthly_deficit:,.2f} this month. This has been deducted from your savings.'
        })

    if cat_expenses:
        top_cat = cat_expenses[0]['category']
        top_amount = cat_expenses[0]['total']
        tips.append({
            'icon': 'alert-circle', 'color': 'danger', 'title': 'Highest Expense Area',
            'body': f'You spent the most on {top_cat} (₹{top_amount:,.2f}) this month.'
        })

    if savings_rate >= float(spending_control.required_saving_threshold):
        tips.append({
            'icon': 'check-circle', 'color': 'success', 'title': 'Savings Target Met',
            'body': f'Great job! Your savings rate ({savings_rate}%) is above your {spending_control.required_saving_threshold}% target.'
        })
    else:
        tips.append({
            'icon': 'target', 'color': 'amber', 'title': 'Savings Target Missed',
            'body': f'Your savings rate ({savings_rate}%) is below your {spending_control.required_saving_threshold}% target.'
        })

    avg_expenses = sum(chart_expenses) / 6 if sum(chart_expenses) > 0 else 0
    if avg_expenses > 0:
        months_covered = ytd_savings / avg_expenses
        tips.append({
            'icon': 'shield', 'color': 'primary', 'title': 'Emergency Fund',
            'body': f'Your YTD savings could cover ~{months_covered:.1f} months of average expenses.'
        })
    
    if best_month_savings > monthly_savings and monthly_savings > 0:
        tips.append({
            'icon': 'trending-up', 'color': 'secondary', 'title': 'Room to Grow',
            'body': f'Your best month was {best_month_label} (₹{best_month_savings:,.2f}). Try to match it!'
        })
    elif monthly_savings > 0:
        tips.append({
            'icon': 'star', 'color': 'success', 'title': 'Top Saver',
            'body': f'This month is shaping up to be your best month for savings!'
        })

    context = {
        'monthly_savings': monthly_savings,
        'monthly_savings_change': monthly_savings_change,
        'monthly_deficit': monthly_deficit,
        'overspent_this_month': overspent_this_month,
        'ytd_overspent': ytd_overspent,
        'effective_ytd_savings': effective_ytd_savings,
        'savings_rate': savings_rate,
        'ytd_savings': ytd_savings,
        'best_month_savings': best_month_savings,
        'best_month_label': best_month_label,
        
        'chart_labels': json.dumps(chart_labels),
        'chart_income': json.dumps(chart_income),
        'chart_expenses': json.dumps(chart_expenses),
        'chart_savings': json.dumps(chart_savings),
        'rate_trend': json.dumps(rate_trend),
        
        'spending_control': spending_control,
        'tips': tips,
    }
    
    return render(request, 'savings/dashboard.html', context)


@login_required(login_url='/authentication/login')
def save_spending_control(request):
    if request.method == 'POST':
        allow_overspending = request.POST.get('allow_overspending') == 'on'
        try:
            threshold = float(request.POST.get('required_saving_threshold', 20.0))
        except ValueError:
            threshold = 20.0
            
        spending_control, created = SpendingControl.objects.get_or_create(owner=request.user)
        spending_control.allow_overspending = allow_overspending
        spending_control.required_saving_threshold = threshold
        spending_control.save()
        
        messages.success(request, 'Spending preferences updated successfully.')
        
    return redirect('savings-dashboard')

# pyrefly: ignore [missing-import]
from django.db.models import Sum
from django.utils import timezone
from datetime import datetime, timedelta
import os
from django.conf import settings


from django.shortcuts import render, redirect,HttpResponseRedirect
from .models import Source, UserIncome
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
import json
from django.http import JsonResponse
import datetime
from django.contrib.auth.decorators import login_required
from datetime import date, timedelta

from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse
from .models import UserIncome
from expenses.models import Expense
from django.db.models import Sum
import csv
import openpyxl
from io import BytesIO
from django.template.loader import get_template
from xhtml2pdf import pisa


from .models import UserIncome
from django.db.models import Sum
from django.db.models.functions import ExtractMonth
from datetime import datetime
# Create your views here.

from decimal import Decimal

def to_decimal(value):
    return Decimal(str(value or 0))
@login_required(login_url='/authentication/login')

def search_income(request):
    if request.method == 'POST':
        search_str = json.loads(request.body).get('searchText')
        income = UserIncome.objects.filter(
            amount__istartswith=search_str, owner=request.user) | UserIncome.objects.filter(
            date__istartswith=search_str, owner=request.user) | UserIncome.objects.filter(
            description__icontains=search_str, owner=request.user) | UserIncome.objects.filter(
            source__icontains=search_str, owner=request.user)
        data = income.values()
        return JsonResponse(list(data), safe=False)


@login_required(login_url='/authentication/login')
def index(request):
    categories = UserIncome.objects.filter(owner=request.user).values('source').distinct().order_by('source')
    income = UserIncome.objects.filter(owner=request.user)

    # Filtering logic
    source = request.GET.get('source')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    amount_min = request.GET.get('amount_min')
    amount_max = request.GET.get('amount_max')
    
    active_filters = False

    if source:
        income = income.filter(source=source)
        active_filters = True
    if date_from:
        income = income.filter(date__gte=date_from)
        active_filters = True
    if date_to:
        income = income.filter(date__lte=date_to)
        active_filters = True
    if amount_min:
        income = income.filter(amount__gte=amount_min)
        active_filters = True
    if amount_max:
        income = income.filter(amount__lte=amount_max)
        active_filters = True

    sort_order = request.GET.get('sort')

    if sort_order == 'amount_asc':
        income = income.order_by('amount')
    elif sort_order == 'amount_desc':
        income = income.order_by('-amount')
    elif sort_order == 'date_asc':
        income = income.order_by('date')
    elif sort_order == 'date_desc':
        income = income.order_by('-date')
    else:
        income = income.order_by('-date')

    paginator = Paginator(income, 5)
    page_number = request.GET.get('page')
    page_obj = Paginator.get_page(paginator, page_number)
    total = page_obj.paginator.num_pages
    
    # Pagination query string builder
    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page']
    filter_query = query_params.urlencode()
    
    context = {
        'sources': categories,
        'income': income,
        'page_obj': page_obj,
        'total': total,
        'sort_order': sort_order,
        'filter_source': source,
        'filter_date_from': date_from,
        'filter_date_to': date_to,
        'filter_amount_min': amount_min,
        'filter_amount_max': amount_max,
        'active_filters': active_filters,
        'filter_query': filter_query,
    }
    return render(request, 'income/index.html', context)

@login_required(login_url='/authentication/login')
def bulk_delete_income(request):
    if request.method == 'POST':
        ids = request.POST.getlist('selected_ids')
        if ids:
            UserIncome.objects.filter(pk__in=ids, owner=request.user).delete()
            messages.success(request, f'{len(ids)} income record(s) deleted.')
    return redirect('income')


@login_required(login_url='/authentication/login')
def add_income(request):
    sources = Source.objects.filter(owner=request.user)
    if(len(sources)==0):
        messages.info(request,"you need to add income sources first in order to add income")
        return HttpResponseRedirect('/account/')
    context = {
        'sources': sources,
        'values': request.POST
    }
    if request.method == 'GET':
        return render(request, 'income/add_income.html', context)

    if request.method == 'POST':
        amount = request.POST['amount']
        date_str = request.POST.get('income_date')
        if not amount:
            messages.error(request, 'Amount is required')
            return render(request, 'income/add_income.html', context)
        description = request.POST['description']
        date = request.POST['income_date']
        source = request.POST['source']

        if not description:
            messages.error(request, 'description is required')
            return render(request, 'income/add_income.html', context)

        try:
            # Convert the date string to a datetime object and validate the date
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            today = datetime.now().date()

            if date > today:
                messages.error(request, 'Date cannot be in the future')
                return render(request, 'income/add_income.html', context)
                # return redirect('add-income', context)

            UserIncome.objects.create(owner=request.user, amount=amount, date=date,
                                      source=source, description=description)
            messages.success(request, 'Income saved successfully')

            return redirect('income')
        except ValueError:
            messages.error(request, 'Invalid date format')
            return render(request, 'income/add_income.html', context)
            # return redirect('add-income', context)

        # UserIncome.objects.create(owner=request.user, amount=amount, date=date,
        #                           source=source, description=description)
        # messages.success(request, 'Record saved successfully')

        # return redirect('income')


@login_required(login_url='/authentication/login')
def income_edit(request, id):
    income = UserIncome.objects.get(pk=id)
    sources = Source.objects.all()
    context = {
        'income': income,
        'values': income,
        'sources': sources
    }
    if request.method == 'GET':
        return render(request, 'income/edit_income.html', context)
    if request.method == 'POST':
        amount = request.POST['amount']
        date_str = request.POST.get('income_date')

        if not amount:
            messages.error(request, 'Amount is required')
            return render(request, 'income/edit_income.html', context)
        description = request.POST['description']
        date = request.POST['income_date']
        source = request.POST['source']

        if not description:
            messages.error(request, 'description is required')
            return render(request, 'income/edit_income.html', context)

        try:
            # Convert the date string to a datetime object and validate the date
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            today = datetime.now().date()

          
            if date > today:
                messages.error(request, 'Date cannot be in the future')
                return render(request, 'income/edit_income.html', context)
                # return redirect('edit_income', context)

            income.amount = amount
            income. date = date
            income.source = source
            income.description = description
            income.save()
            messages.success(request, 'Income saved successfully')

            return redirect('income')
        except ValueError:
            messages.error(request, 'Invalid date format')
            return render(request, 'income/edit_income.html', context)
        # income.amount = amount
        # income. date = date
        # income.source = source
        # income.description = description

        # income.save()
        # messages.success(request, 'Record updated  successfully')

        # return redirect('income')

@login_required(login_url='/authentication/login')
def delete_income(request, id):
    income = UserIncome.objects.get(pk=id)
    income.delete()
    messages.success(request, 'record removed')
    return redirect('income')


@login_required(login_url='/authentication/login')
def income_summary(request):
    user = request.user  # Get the logged-in user

    today = timezone.now().date()
    one_week_ago = today - timedelta(days=7)
    first_day_of_month = today.replace(day=1)
    first_day_of_year = today.replace(month=1, day=1)

    # Query the database to get daily, weekly, monthly, and yearly income for the logged-in user
    daily_income = to_decimal(user.userincome_set.filter(date=today).exclude(source__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or 0)
    weekly_income = to_decimal(user.userincome_set.filter(date__range=[one_week_ago, today]).exclude(source__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or 0)
    monthly_income = to_decimal(user.userincome_set.filter(date__month=today.month, date__year=today.year).exclude(source__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or 0)
    yearly_income = to_decimal(user.userincome_set.filter(date__year=today.year).exclude(source__icontains='Investment').aggregate(Sum('amount'))['amount__sum'] or 0)

    context = {
        'daily_income': daily_income,
        'weekly_income': weekly_income,
        'monthly_income': monthly_income,
        'yearly_income': yearly_income,
        # You can add more context data here if needed
    }
    return render(request, 'income/dashboard.html', context)

# @login_required(login_url='/authentication/login')
# def income_summary(request):
#     today = timezone.now()

#     # Calculate the date for one week ago
#     one_week_ago = today - timedelta(days=7)

#     # Calculate the first day of the current month
#     first_day_of_month = today.replace(day=1)
#     first_day_of_year = today.replace(month=1, day=1)

#     # Query the database to get daily, weekly, and monthly income
#     daily_income = UserIncome.objects.filter(date=today).aggregate(Sum('amount'))['amount__sum'] or 0
#     weekly_income = UserIncome.objects.filter(date__range=[one_week_ago, today]).aggregate(Sum('amount'))['amount__sum'] or 0
#     monthly_income = UserIncome.objects.filter(date__month=today.month).aggregate(Sum('amount'))['amount__sum'] or 0
#     yearly_income = UserIncome.objects.filter(date__year=today.year).aggregate(Sum('amount'))['amount__sum'] or 0
#     context = {
#         'daily_income': daily_income,
#         'weekly_income': weekly_income,
#         'monthly_income': monthly_income,
#         'yearly_income': yearly_income,
#         # You can add more context data here if needed
#     }
#     return render(request,'income/dashboard.html',context)




from datetime import datetime

@login_required(login_url='/authentication/login')
def monthly_income_data(request):
    current_year = datetime.now().year

    monthly_data = list(
        UserIncome.objects
        .filter(owner=request.user, date__year=current_year)
        .exclude(source__icontains='Investment')
        .annotate(month=ExtractMonth('date'))
        .values('month')
        .annotate(total_income=Sum('amount'))
        .order_by('month')
    )

    expense_data = list(
        Expense.objects
        .filter(owner=request.user, date__year=current_year)
        .exclude(category__icontains='Investment')
        .annotate(month=ExtractMonth('date'))
        .values('month')
        .annotate(total_expense=Sum('amount'))
        .order_by('month')
    )

    source_qs = list(
        UserIncome.objects
        .filter(owner=request.user, date__year=current_year)
        .exclude(source__icontains='Investment')
        .annotate(month=ExtractMonth('date'))
        .values('source', 'month')
        .annotate(total=Sum('amount'))
    )

    months_present = set()
    for item in monthly_data:
        months_present.add(item['month'])
    for item in expense_data:
        months_present.add(item['month'])
    for item in source_qs:
        months_present.add(item['month'])

    months_present = sorted(list(months_present))
    
    # If no data at all, fallback to current month
    if not months_present:
        months_present = [datetime.now().month]

    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    labels = [month_names[m - 1] for m in months_present]

    monthly_income_data = []
    monthly_expense_data = []

    def get_val(data_list, key, m):
        for d in data_list:
            if d['month'] == m:
                return float(d[key] or 0)
        return 0.0

    for m in months_present:
        monthly_income_data.append(get_val(monthly_data, 'total_income', m))
        monthly_expense_data.append(get_val(expense_data, 'total_expense', m))

    source_data = {}
    for item in source_qs:
        src = item['source']
        if not src:
            src = "Other"
        if src not in source_data:
            source_data[src] = [0] * len(months_present)

    for item in source_qs:
        src = item['source']
        if not src:
            src = "Other"
        month_idx = months_present.index(item['month'])
        source_data[src][month_idx] = float(item['total'] or 0)

    return JsonResponse({
        'labels': labels,
        'monthly_income_data': monthly_income_data,
        'monthly_expense_data': monthly_expense_data,
        'source_data': source_data
    })

@login_required(login_url='/authentication/login')
def income_vs_expense_data(request):
    current_year = datetime.now().year
    
    monthly_income = [0] * 12
    monthly_expense = [0] * 12
    
    income_data = (
        UserIncome.objects
        .filter(owner=request.user, date__year=current_year, source__icontains='Investment')
        .annotate(month=ExtractMonth('date'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )
    for item in income_data:
        monthly_income[item['month'] - 1] = float(item['total'] or 0)
        
    expense_data = (
        Expense.objects
        .filter(owner=request.user, date__year=current_year, category__icontains='Investment')
        .annotate(month=ExtractMonth('date'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )
    for item in expense_data:
        monthly_expense[item['month'] - 1] = float(item['total'] or 0)
        
    return JsonResponse({
        'income_data': monthly_income,
        'expense_data': monthly_expense
    })

@login_required(login_url='/authentication/login')
def get_monthly_income(request):
    today = date.today()
    first_day_of_year = today.replace(month=1, day=1)
    last_day_of_year = today.replace(month=12, day=31)

    # Create a list to hold income data for all 12 months
    monthly_data = [0] * 12

    # Retrieve and fill in the actual monthly income data
    income_data = UserIncome.objects.filter(
        date__range=(first_day_of_year, last_day_of_year),
        owner=request.user
    ).exclude(source__icontains='Investment').values('date', 'amount')

    for entry in income_data:
        month = entry['date'].month - 1  # Convert month (1-12) to index (0-11)
        monthly_data[month] = float(entry['amount'] or 0)

    return JsonResponse({'monthly_data': monthly_data})





def render_to_pdf(template_path, context_dict):
    template = get_template(template_path)
    html = template.render(context_dict)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="expense_report.pdf"'
        return response
    return HttpResponse("Error rendering PDF", status=400)


@login_required(login_url='/authentication/login')
def export_pdf(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    incomes = UserIncome.objects.filter(owner=request.user, date__range=[start_date, end_date]).exclude(source__icontains='Investment').order_by('-date', '-amount')
    expenses = Expense.objects.filter(owner=request.user, date__range=[start_date, end_date]).exclude(category__icontains='Investment').order_by('-date')
    
    total_income = to_decimal(incomes.aggregate(Sum('amount'))['amount__sum'] or 0)
    total_expense = to_decimal(expenses.aggregate(Sum('amount'))['amount__sum'] or 0)
    
    savings = total_income - total_expense
    
    expenses_by_category = expenses.values('category').annotate(total_amount=Sum('amount')).order_by('-total_amount')
    
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'finsight_logo.png')

    context = {
        'incomes': incomes,
        'expenses': expenses,
        'total_income': total_income,
        'total_expense': total_expense,
        'savings': savings,
        'start_date': start_date,
        'end_date': end_date,
        'expenses_by_category': expenses_by_category,
        'logo_path': logo_path,
    }
    
    pdf = render_to_pdf('income/pdf_template.html', context)
    return pdf

@login_required(login_url='/authentication/login')
def report(request):
    report_generated=False
    return render(request, 'income/report.html',{'report_generated':report_generated})

def generate_report(request):
    if request.method == "POST":
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        user = request.user
        report_generated=True

        if start_date > end_date:
            messages.error(request, "Start date cannot be greater than end date.")
            return redirect('report')

        # incomes = UserIncome.objects.filter(date__range=[start_date, end_date])
        # expenses = Expense.objects.filter(date__range=[start_date, end_date])

        incomes = UserIncome.objects.filter(owner=user, date__range=[start_date, end_date]).exclude(source__icontains='Investment').order_by('-date', '-amount')
        expenses = Expense.objects.filter(owner=user, date__range=[start_date, end_date]).exclude(category__icontains='Investment').order_by('-date')

        total_income = to_decimal(incomes.aggregate(Sum('amount'))['amount__sum'] or 0)
        total_expense = to_decimal(expenses.aggregate(Sum('amount'))['amount__sum'] or 0)

        savings = total_income - total_expense
        
        context = {
            'incomes': incomes,
            'expenses': expenses,
            'total_income': total_income,
            'total_expense': total_expense,
            'savings': savings,
            'start_date': start_date,
            'end_date': end_date,
            'report_generated':report_generated
        }

        return render(request, 'income/report.html', context)
    else:
        
        return render(request, 'income/report.html')

@login_required(login_url='/authentication/login')
def export_csv(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    incomes = UserIncome.objects.filter(owner=request.user, date__range=[start_date, end_date]).exclude(source__icontains='Investment')
    expenses = Expense.objects.filter(owner=request.user, date__range=[start_date, end_date]).exclude(category__icontains='Investment')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="report_{start_date}_to_{end_date}.csv'
    
    writer = csv.writer(response)
    
    # Label the income section
    writer.writerow(['Income'])
    writer.writerow(['Date', 'Source', 'Amount'])
    
    income_total = 0
    for income in incomes:
        writer.writerow([income.date, income.source, income.amount])
        income_total += income.amount
    
    # Display the total income
    writer.writerow(['', f'Total Income: {income_total}'])

    # Label the expense section
    writer.writerow(['Expenses'])
    writer.writerow(['Date', 'Category', 'Amount'])
    
    expense_total = 0
    for expense in expenses:
        writer.writerow([expense.date, expense.category, expense.amount])
        expense_total += expense.amount
    
    # Add an empty line
    writer.writerow([])
    
    # Display the total expense
    writer.writerow(['', f'Total Expenses: {expense_total}'])
    
    return response

@login_required(login_url='/authentication/login')
def export_xlsx(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    incomes = UserIncome.objects.filter(owner=request.user, date__range=[start_date, end_date]).exclude(source__icontains='Investment')
    expenses = Expense.objects.filter(owner=request.user, date__range=[start_date, end_date]).exclude(category__icontains='Investment')
    
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = f'attachment; filename="report_{start_date}_to_{end_date}.xlsx"'
    
    wb = openpyxl.Workbook()
    ws = wb.active
    
    # Label the income section
    ws.append(['Income'])
    ws.append(['Date', 'Source', 'Amount'])
    
    income_total = 0
    for income in incomes:
        ws.append([income.date, income.source, income.amount])
        income_total += income.amount
    
    # Display the total income
    ws.append(['', f'Total Income: {income_total}'])

    # Label the expense section
    ws.append(['Expenses'])
    ws.append(['Date', 'Category', 'Amount'])
    
    expense_total = 0
    for expense in expenses:
        ws.append([expense.date, expense.category, expense.amount])
        expense_total += expense.amount
    
    # Add an empty line
    ws.append([])
    
    # Display the total expense
    ws.append(['', f'Total Expenses: {expense_total}'])
    
    wb.save(response)
    return response

import pandas as pd
from django.utils.dateparse import parse_date
import math

@login_required(login_url='/authentication/login')
def bulk_import_income(request):
    if request.method == 'GET':
        return render(request, 'income/bulk_import.html')

    if request.method == 'POST':
        if 'file' not in request.FILES:
            messages.error(request, 'Please upload a valid CSV or Excel file.')
            return redirect('bulk-import-income')
            
        file = request.FILES['file']
        filename = file.name
        
        try:
            if filename.endswith('.csv'):
                df = pd.read_csv(file)
            elif filename.endswith('.xlsx') or filename.endswith('.xls'):
                df = pd.read_excel(file)
            else:
                messages.error(request, 'Unsupported file format. Please upload .csv or .xlsx')
                return redirect('bulk-import-income')
                
            # Normalize column names
            df.columns = [str(col).strip().lower() for col in df.columns]
            
            required_columns = {'date', 'description', 'amount'}
            if not required_columns.issubset(set(df.columns)):
                messages.error(request, f'Missing required columns. Expected at least: date, description, amount. Found: {", ".join(df.columns)}')
                return redirect('bulk-import-income')

            imported_count = 0
            skipped_count = 0

            for index, row in df.iterrows():
                try:
                    # Validate Date
                    raw_date = row['date']
                    if pd.isna(raw_date):
                        skipped_count += 1
                        continue
                    
                    if isinstance(raw_date, str):
                        income_date = parse_date(raw_date)
                        if not income_date:
                            income_date = pd.to_datetime(raw_date).date()
                    else:
                        income_date = raw_date.date() if hasattr(raw_date, 'date') else pd.to_datetime(raw_date).date()
                    
                    if income_date > date.today():
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

                    # Source Logic (Default to 'Other' if empty)
                    source = str(row.get('source', '')).strip()
                    if pd.isna(row.get('source')) or not source or source == 'nan':
                        source = 'Other'

                    # Save Income
                    UserIncome.objects.create(
                        owner=request.user,
                        amount=amount,
                        date=income_date,
                        description=description,
                        source=source
                    )
                    imported_count += 1
                except Exception as e:
                    print(f"Row {index} failed: {e}")
                    skipped_count += 1
                    continue

            messages.success(request, f'Successfully imported {imported_count} income records. Skipped {skipped_count} invalid rows.')
            return redirect('income')

        except Exception as e:
            messages.error(request, f'Error processing file: {str(e)}')
            return redirect('bulk-import-income')


from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from .models import Investment
import csv
from collections import defaultdict
from datetime import datetime
@login_required(login_url='/authentication/login')
def investment_dashboard(request):
    return render(request, 'investments/dashboard.html')

@login_required(login_url='/authentication/login')
def investment_data(request):
    investments = Investment.objects.filter(owner=request.user)

    total_invested = 0.0
    total_returns = 0.0

    monthly_data = {}
    asset_invested = {}
    
    grouped_detailed = {}
    grouped_basic = {}

    def get_month_key(d):
        return d.strftime("%b %Y"), d.replace(day=1)

    for inv in investments:
        amt_invested = float(inv.amount_invested)
        amt_returns = float(inv.returns)
        
        total_invested += amt_invested
        total_returns += amt_returns
        
        m_key_inv, m_date_inv = get_month_key(inv.date)
        if m_key_inv not in monthly_data:
            monthly_data[m_key_inv] = {'invested': 0.0, 'returns': 0.0, 'dateObj': m_date_inv}
        monthly_data[m_key_inv]['invested'] += amt_invested
        
        if inv.sell_date:
            m_key_ret, m_date_ret = get_month_key(inv.sell_date)
            if m_key_ret not in monthly_data:
                monthly_data[m_key_ret] = {'invested': 0.0, 'returns': 0.0, 'dateObj': m_date_ret}
            monthly_data[m_key_ret]['returns'] += amt_returns
            
        asset_type = inv.investment_type
        portfolio = inv.name
        
        asset_invested[asset_type] = asset_invested.get(asset_type, 0.0) + amt_invested
        
        det_key = f"{asset_type} - {portfolio}"
        if det_key not in grouped_detailed:
            grouped_detailed[det_key] = {'name': det_key, 'invested': 0.0, 'returns': 0.0}
        grouped_detailed[det_key]['invested'] += amt_invested
        grouped_detailed[det_key]['returns'] += amt_returns
        
        if asset_type not in grouped_basic:
            grouped_basic[asset_type] = {'name': asset_type, 'invested': 0.0, 'returns': 0.0}
        grouped_basic[asset_type]['invested'] += amt_invested
        grouped_basic[asset_type]['returns'] += amt_returns

    net_pnl = total_returns - total_invested
    pnl_pct = round((net_pnl / total_invested) * 100, 1) if total_invested > 0 else 0.0

    sorted_months = sorted(monthly_data.items(), key=lambda x: x[1]['dateObj'])
    best_month = 'N/A'
    max_profit = float('-inf')
    
    bar_labels = []
    bar_invested = []
    bar_returns = []
    bar_net_pnl = []

    for m_key, data in sorted_months:
        profit = data['returns'] - data['invested']
        if profit > max_profit:
            max_profit = profit
            best_month = m_key
        
        bar_labels.append(m_key)
        bar_invested.append(data['invested'])
        bar_returns.append(data['returns'])
        bar_net_pnl.append(profit)

    if max_profit == float('-inf') or not sorted_months:
        max_profit = 0.0
        best_month = 'N/A'

    def process_table(group_dict):
        result = []
        for v in group_dict.values():
            pnl = v['returns'] - v['invested']
            pnl_pct = round((pnl / v['invested']) * 100, 1) if v['invested'] > 0 else 0.0
            result.append({
                'name': v['name'],
                'invested': v['invested'],
                'returns': v['returns'],
                'pnl': pnl,
                'pnl_pct': pnl_pct
            })
        return sorted(result, key=lambda x: x['invested'], reverse=True)

    table_detailed = process_table(grouped_detailed)
    table_basic = process_table(grouped_basic)

    return JsonResponse({
        "summary": {
            "total_invested": total_invested,
            "total_returns": total_returns,
            "net_pnl": net_pnl,
            "pnl_pct": pnl_pct,
            "best_month": best_month,
            "best_month_returns": max_profit
        },
        "charts": {
            "donut": {
                "labels": list(asset_invested.keys()),
                "data": list(asset_invested.values())
            },
            "bar": {
                "labels": bar_labels,
                "invested": bar_invested,
                "returns": bar_returns,
                "net_pnl": bar_net_pnl
            }
        },
        "table_data": {
            "detailed": table_detailed,
            "basic": table_basic
        }
    })

@login_required(login_url='/authentication/login')
def export_investments_csv(request):
    investments = Investment.objects.filter(owner=request.user)

    # Group by assetType + portfolio combination
    inv_by_combo = defaultdict(lambda: {'invested': 0.0, 'returned': 0.0})
    
    for inv in investments:
        combo = f"{inv.investment_type} - {inv.name}"
        inv_by_combo[combo]['invested'] += float(inv.amount_invested)
        inv_by_combo[combo]['returned'] += float(inv.returns)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="investment_report.csv"'

    writer = csv.writer(response)
    writer.writerow(['Name / Description', 'Invested', 'Returns', 'P&L (Rs)', 'P&L (%)', 'Status'])

    for desc, data in sorted(inv_by_combo.items()):
        invested = data['invested']
        returned = data['returned']
        pnl = returned - invested
        pnl_pct = round((pnl / invested * 100), 1) if invested > 0 else 0.0
        status = 'Profit' if pnl > 0 else ('Loss' if pnl < 0 else 'Break Even')
        writer.writerow([desc, round(invested, 2), round(returned, 2), round(pnl, 2), pnl_pct, status])

    return response

from django.core.paginator import Paginator
from django.contrib import messages
import json
from decimal import Decimal
import pandas as pd
import math
from django.utils.dateparse import parse_date
from expenses.views import check_two_tier_guard

@login_required(login_url='/authentication/login')
def investment_list(request):
    investments = Investment.objects.filter(owner=request.user).order_by('-date')
    
    # Filter logic
    search_q = request.GET.get('q')
    status = request.GET.get('status')
    inv_type = request.GET.get('type')
    
    active_filters = False
    
    if search_q:
        investments = investments.filter(name__icontains=search_q)
        active_filters = True
    if status:
        investments = investments.filter(status=status)
        active_filters = True
    if inv_type:
        investments = investments.filter(investment_type=inv_type)
        active_filters = True
        
    sort_order = request.GET.get('sort')
    if sort_order == 'amount_asc':
        investments = investments.order_by('amount_invested')
    elif sort_order == 'amount_desc':
        investments = investments.order_by('-amount_invested')
    elif sort_order == 'date_asc':
        investments = investments.order_by('date')
    elif sort_order == 'date_desc':
        investments = investments.order_by('-date')
    else:
        investments = investments.order_by('-date')
        
    # Calculate Net P&L
    for inv in investments:
        inv.net_pnl = float(inv.returns) - float(inv.amount_invested)
        
    paginator = Paginator(investments, 5)
    page_number = request.GET.get('page')
    page_obj = Paginator.get_page(paginator, page_number)
    
    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page']
    filter_query = query_params.urlencode()
    
    types = Investment._meta.get_field('investment_type').choices
    
    context = {
        'investments': investments,
        'page_obj': page_obj,
        'active_filters': active_filters,
        'filter_query': filter_query,
        'types': types,
        'filter_type': inv_type,
        'filter_status': status,
        'search_q': search_q,
    }
    return render(request, 'investments/index.html', context)

@login_required(login_url='/authentication/login')
def add_investment(request):
    types = Investment._meta.get_field('investment_type').choices
    context = {'types': types, 'values': request.POST}
    
    if request.method == 'GET':
        return render(request, 'investments/add_investment.html', context)
        
    if request.method == 'POST':
        name = request.POST.get('name')
        investment_type = request.POST.get('investment_type')
        amount_str = request.POST.get('amount_invested')
        returns_str = request.POST.get('returns', '0')
        date_str = request.POST.get('date')
        sell_date_str = request.POST.get('sell_date')
        status = request.POST.get('status', 'Active')
        notes = request.POST.get('notes', '')
        
        if not name or not investment_type or not amount_str or not date_str:
            messages.error(request, 'Name, Type, Amount, and Date are required')
            return render(request, 'investments/add_investment.html', context)
            
        try:
            amount_invested = Decimal(amount_str)
            returns = Decimal(returns_str) if returns_str else Decimal('0')
            inv_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            sell_date = None
            if status == 'Sold' and sell_date_str:
                sell_date = datetime.strptime(sell_date_str, '%Y-%m-%d').date()
                if sell_date < inv_date:
                    messages.error(request, 'Sell Date cannot be before Date of Investment')
                    return render(request, 'investments/add_investment.html', context)
            
            # Tier Check Logic
            tier_2_blocked, tier_1_warning, drawdown_amount, cumulative_savings = check_two_tier_guard(request.user, amount_invested)
            force_save = request.POST.get('force_save') == '1'
            
            from savings.models import SpendingControl
            spending_control = SpendingControl.objects.filter(owner=request.user).first()
            allow_overspending = spending_control.allow_overspending if spending_control else True
            
            if tier_2_blocked:
                messages.error(request, f'Transaction Blocked: This investment of ₹{amount_invested:,.2f} would exceed your total available funds. You have ₹{cumulative_savings:,.2f} available across income and savings.')
                return render(request, 'investments/add_investment.html', context)
                
            if tier_1_warning:
                if not allow_overspending:
                    messages.error(request, f'Transaction Blocked: You have exceeded this month\'s income. Overspending is disabled. Enable it in Settings → Limits to draw from savings.')
                    return render(request, 'investments/add_investment.html', context)
                elif not force_save:
                    messages.warning(request, f'Warning: This investment exceeds your income for this month. You will be drawing ₹{drawdown_amount:,.2f} from your savings. Available savings: ₹{cumulative_savings:,.2f}. Do you want to continue?')
                    return render(request, 'investments/add_investment.html', context)
                    
            Investment.objects.create(
                owner=request.user, name=name, investment_type=investment_type,
                amount_invested=amount_invested, returns=returns,
                date=inv_date, sell_date=sell_date, status=status, notes=notes
            )
            messages.success(request, 'Investment added successfully')
            return redirect('investments')
            
        except ValueError:
            messages.error(request, 'Invalid input format (Date or Amount)')
            return render(request, 'investments/add_investment.html', context)

@login_required(login_url='/authentication/login')
def edit_investment(request, id):
    inv = Investment.objects.get(pk=id, owner=request.user)
    types = Investment._meta.get_field('investment_type').choices
    
    # Pre-populate dates for HTML inputs
    inv_date_str = inv.date.strftime('%Y-%m-%d') if inv.date else ''
    sell_date_str = inv.sell_date.strftime('%Y-%m-%d') if inv.sell_date else ''
    
    context = {'inv': inv, 'investment_id': inv.id, 'types': types, 'values': request.POST or {
        'name': inv.name, 'investment_type': inv.investment_type,
        'amount_invested': inv.amount_invested, 'returns': inv.returns,
        'date': inv_date_str, 'sell_date': sell_date_str,
        'status': inv.status, 'notes': inv.notes
    }}
    
    if request.method == 'GET':
        return render(request, 'investments/edit_investment.html', context)
        
    if request.method == 'POST':
        name = request.POST.get('name')
        investment_type = request.POST.get('investment_type')
        amount_str = request.POST.get('amount_invested')
        returns_str = request.POST.get('returns', '0')
        date_str = request.POST.get('date')
        sell_date_str = request.POST.get('sell_date')
        status = request.POST.get('status', 'Active')
        notes = request.POST.get('notes', '')
        
        if not name or not investment_type or not amount_str or not date_str:
            messages.error(request, 'Name, Type, Amount, and Date are required')
            return render(request, 'investments/edit_investment.html', context)
            
        try:
            amount_invested = Decimal(amount_str)
            returns = Decimal(returns_str) if returns_str else Decimal('0')
            inv_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            sell_date = None
            if status == 'Sold' and sell_date_str:
                sell_date = datetime.strptime(sell_date_str, '%Y-%m-%d').date()
                if sell_date < inv_date:
                    messages.error(request, 'Sell Date cannot be before Date of Investment')
                    return render(request, 'investments/edit_investment.html', context)
            
            # Check funds only if amount increased
            amount_diff = amount_invested - inv.amount_invested
            if amount_diff > 0:
                tier_2_blocked, tier_1_warning, drawdown_amount, cumulative_savings = check_two_tier_guard(request.user, amount_invested, inv.id)
                force_save = request.POST.get('force_save') == '1'
                
                from savings.models import SpendingControl
                spending_control = SpendingControl.objects.filter(owner=request.user).first()
                allow_overspending = spending_control.allow_overspending if spending_control else True
                
                if tier_2_blocked:
                    messages.error(request, f'Transaction Blocked: This investment of ₹{amount_invested:,.2f} would exceed your total available funds. You have ₹{cumulative_savings:,.2f} available across income and savings.')
                    return render(request, 'investments/edit_investment.html', context)
                    
                if tier_1_warning:
                    if not allow_overspending:
                        messages.error(request, f'Transaction Blocked: You have exceeded this month\'s income. Overspending is disabled. Enable it in Settings → Limits to draw from savings.')
                        return render(request, 'investments/edit_investment.html', context)
                    elif not force_save:
                        messages.warning(request, f'Warning: This investment exceeds your income for this month. You will be drawing ₹{drawdown_amount:,.2f} from your savings. Available savings: ₹{cumulative_savings:,.2f}. Do you want to continue?')
                        return render(request, 'investments/edit_investment.html', context)
            
            inv.name = name
            inv.investment_type = investment_type
            inv.amount_invested = amount_invested
            inv.returns = returns
            inv.date = inv_date
            inv.sell_date = sell_date
            inv.status = status
            inv.notes = notes
            inv.save()
            
            messages.success(request, 'Investment updated successfully')
            return redirect('investments')
            
        except ValueError:
            messages.error(request, 'Invalid input format (Date or Amount)')
            return render(request, 'investments/edit_investment.html', context)

@login_required(login_url='/authentication/login')
def delete_investment(request, id):
    inv = Investment.objects.get(pk=id, owner=request.user)
    inv.delete()
    messages.success(request, 'Investment removed successfully')
    return redirect('investments')

@login_required(login_url='/authentication/login')
def bulk_delete_investments(request):
    if request.method == 'POST':
        ids = request.POST.getlist('selected_ids')
        if ids:
            Investment.objects.filter(pk__in=ids, owner=request.user).delete()
            messages.success(request, f'{len(ids)} investment(s) deleted.')
    return redirect('investments')

@login_required(login_url='/authentication/login')
def search_investments(request):
    if request.method == 'POST':
        search_str = json.loads(request.body).get('searchText')
        investments = Investment.objects.filter(
            name__icontains=search_str, owner=request.user) | Investment.objects.filter(
            investment_type__icontains=search_str, owner=request.user) | Investment.objects.filter(
            status__icontains=search_str, owner=request.user)
        
        data = list(investments.values())
        for item in data:
            item['net_pnl'] = float(item['returns']) - float(item['amount_invested'])
        return JsonResponse(data, safe=False)

@login_required(login_url='/authentication/login')
def bulk_import_investments(request):
    if request.method == 'GET':
        return render(request, 'investments/bulk_import.html')

    if request.method == 'POST':
        if 'file' not in request.FILES:
            messages.error(request, 'Please upload a valid CSV or Excel file.')
            return redirect('bulk_import_investments')
            
        file = request.FILES['file']
        filename = file.name
        
        try:
            if filename.endswith('.csv'):
                df = pd.read_csv(file)
            elif filename.endswith('.xlsx') or filename.endswith('.xls'):
                df = pd.read_excel(file)
            else:
                messages.error(request, 'Unsupported file format. Please upload .csv or .xlsx')
                return redirect('bulk_import_investments')
                
            df.columns = [str(col).strip().lower() for col in df.columns]
            
            required_columns = {'name', 'amount_invested', 'date'}
            if not required_columns.issubset(set(df.columns)):
                messages.error(request, f'Missing required columns. Expected at least: name, amount_invested, date. Found: {", ".join(df.columns)}')
                return redirect('bulk_import_investments')

            imported_count = 0
            skipped_count = 0

            for index, row in df.iterrows():
                try:
                    name = str(row['name']).strip()
                    if pd.isna(row['name']) or not name or name == 'nan':
                        skipped_count += 1
                        continue

                    raw_date = row['date']
                    if pd.isna(raw_date):
                        skipped_count += 1
                        continue
                    
                    if isinstance(raw_date, str):
                        inv_date = parse_date(raw_date)
                        if not inv_date:
                            inv_date = pd.to_datetime(raw_date).date()
                    else:
                        inv_date = raw_date.date() if hasattr(raw_date, 'date') else pd.to_datetime(raw_date).date()
                    
                    amount_invested = Decimal(str(row['amount_invested']))
                    if math.isnan(amount_invested) or amount_invested <= 0:
                        skipped_count += 1
                        continue

                    inv_type = str(row.get('investment_type', 'Other')).strip()
                    if pd.isna(row.get('investment_type')) or not inv_type or inv_type == 'nan':
                        inv_type = 'Other'
                        
                    returns_val = row.get('returns', 0)
                    if pd.isna(returns_val):
                        returns_val = 0
                    returns = Decimal(str(returns_val))
                    
                    status = str(row.get('status', 'Active')).strip()
                    if pd.isna(row.get('status')) or not status or status == 'nan':
                        status = 'Active'

                    Investment.objects.create(
                        owner=request.user,
                        name=name,
                        investment_type=inv_type,
                        amount_invested=amount_invested,
                        returns=returns,
                        date=inv_date,
                        status=status,
                    )
                    imported_count += 1
                except Exception as e:
                    print(f"Row {index} failed: {e}")
                    skipped_count += 1
                    continue

            messages.success(request, f'Successfully imported {imported_count} investments. Skipped {skipped_count} invalid rows.')
            return redirect('investments')

        except Exception as e:
            messages.error(request, f'Error processing file: {str(e)}')
            return redirect('bulk_import_investments')

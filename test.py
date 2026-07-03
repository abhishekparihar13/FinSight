import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expensetracker.settings')
django.setup()

from expenses.models import Expense
from django.contrib.auth.models import User

user = User.objects.first()
print("Total expenses:", Expense.objects.filter(owner=user).count())

search_str = ""
expenses = Expense.objects.filter(
    amount__istartswith=search_str, owner=user) | Expense.objects.filter(
    date__istartswith=search_str, owner=user) | Expense.objects.filter(
    description__icontains=search_str, owner=user) | Expense.objects.filter(
    category__icontains=search_str, owner=user)
print("Searched expenses:", expenses.count())

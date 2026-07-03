from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now

# Create your models here.


class Expense(models.Model):
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(default=now)
    description = models.TextField()
    owner = models.ForeignKey(to=User, on_delete=models.CASCADE)
    category = models.CharField(max_length=266)

    def __str__(self):
        return self.category

    class Meta:
        ordering=['-date']


class Category(models.Model):
    name = models.CharField(max_length=255)

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

class ExpenseLimit(models.Model):
    owner = models.ForeignKey(to=User, on_delete=models.CASCADE)
    daily_expense_limit=models.IntegerField(default=0)
    weekly_expense_limit=models.IntegerField(default=0)
    monthly_expense_limit=models.IntegerField(default=0)
    yearly_expense_limit=models.IntegerField(default=0)

class Notification(models.Model):
    user = models.ForeignKey(to=User, on_delete=models.CASCADE)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    period = models.CharField(max_length=50)
    threshold = models.IntegerField()
    date_triggered = models.DateField(default=now)

    class Meta:
        ordering = ['-created_at']

class RecurringExpense(models.Model):
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.CharField(max_length=266)
    description = models.TextField()
    owner = models.ForeignKey(to=User, on_delete=models.CASCADE)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    next_due_date = models.DateField(default=now)

    def __str__(self):
        return f"{self.category} - {self.frequency}"

    class Meta:
        ordering = ['next_due_date']



class PendingRecurringExpense(models.Model):
    recurring_expense = models.ForeignKey(RecurringExpense, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.CharField(max_length=266)
    description = models.TextField()
    owner = models.ForeignKey(to=User, on_delete=models.CASCADE)
    due_date = models.DateField(default=now)
    
    class Meta:
        ordering = ['-due_date']

    def __str__(self):
        return f"Pending: {self.category} - {self.amount}"

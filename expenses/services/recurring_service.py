from expenses.models import RecurringExpense, PendingRecurringExpense
from django.core.mail import send_mail
from django.conf import settings
from datetime import date
import datetime
from dateutil.relativedelta import relativedelta
import threading

def process_due_recurring_expenses():
    today = date.today()
    due_expenses = RecurringExpense.objects.filter(next_due_date__lte=today)
    
    for recur in due_expenses:
        # Create the pending expense record
        PendingRecurringExpense.objects.create(
            recurring_expense=recur,
            amount=recur.amount,
            due_date=today,
            description=recur.description,
            owner=recur.owner,
            category=recur.category
        )
        
        # Send Email (Without creating an in-app Notification to avoid duplicates)
        msg = f"Your recurring expense '{recur.description}' of amount ₹{recur.amount} is due. Please log in and confirm payment."
        if recur.owner.email:
            try:
                send_mail(
                    subject='FinSight: Recurring Expense Due',
                    message=msg,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recur.owner.email],
                    fail_silently=True,
                )
            except Exception as e:
                pass
        
        # Calculate next due date
        if recur.frequency == 'daily':
            recur.next_due_date = today + datetime.timedelta(days=1)
        elif recur.frequency == 'weekly':
            recur.next_due_date = today + datetime.timedelta(weeks=1)
        elif recur.frequency == 'monthly':
            recur.next_due_date = today + relativedelta(months=1)
            
        recur.save()

def process_due_recurring_expenses_async():
    """Runs the processing logic in a background thread to avoid blocking the request."""
    thread = threading.Thread(target=process_due_recurring_expenses)
    thread.start()

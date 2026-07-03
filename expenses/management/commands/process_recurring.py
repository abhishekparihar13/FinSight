from django.core.management.base import BaseCommand
from expenses.models import RecurringExpense, PendingRecurringExpense, Notification
from django.core.mail import send_mail
from django.conf import settings
from datetime import date
from dateutil.relativedelta import relativedelta
import datetime

class Command(BaseCommand):
    help = 'Process recurring expenses that are due and generate pending records.'

    def handle(self, *args, **options):
        today = date.today()
        due_expenses = RecurringExpense.objects.filter(next_due_date__lte=today)
        
        count = 0
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
            
            # Send Email
            msg = f"Your recurring expense '{recur.description}' of amount ₹{recur.amount} is due. Please confirm payment."

            # Send Email
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
                    self.stderr.write(f"Failed to send email to {recur.owner.email}: {e}")
            
            # Calculate next due date
            if recur.frequency == 'daily':
                recur.next_due_date = today + datetime.timedelta(days=1)
            elif recur.frequency == 'weekly':
                recur.next_due_date = today + datetime.timedelta(weeks=1)
            elif recur.frequency == 'monthly':
                recur.next_due_date = today + relativedelta(months=1)
                
            recur.save()
            count += 1
            
        self.stdout.write(self.style.SUCCESS(f'Successfully processed {count} recurring expenses.'))

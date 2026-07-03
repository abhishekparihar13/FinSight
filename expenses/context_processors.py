from .models import Notification, PendingRecurringExpense
from expenses.services.recurring_service import process_due_recurring_expenses_async

def notifications(request):
    if request.user.is_authenticated:
        # Automate the processing of due recurring expenses
        process_due_recurring_expenses_async()
        
        unread_notifications = Notification.objects.filter(user=request.user, is_read=False).order_by('-created_at')
        pending_expenses = PendingRecurringExpense.objects.filter(owner=request.user).order_by('due_date')
        return {
            'unread_notifications': unread_notifications,
            'pending_recurring_expenses': pending_expenses
        }
    return {
        'unread_notifications': [],
        'pending_recurring_expenses': []
    }

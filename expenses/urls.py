from django.urls import path
from . import views

from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path('', views.index, name="expenses"),
    path('add-expense', views.add_expense, name="add-expenses"),
    path('edit-expense/<int:id>', views.expense_edit, name="expense-edit"),
    path('expense-delete/<int:id>', views.delete_expense, name="expense-delete"),
    path('search-expenses', csrf_exempt(views.search_expenses),
         name="search_expenses"),
    path('expense_category_summary', views.expense_category_summary,
         name="expense_category_summary"),
    path('stats', views.stats_view,
         name="stats"),
    path('set-daily-expense-limit/',views.set_expense_limit,name="set-daily-expense-limit"),
    path('mark-notifications-read/', views.mark_notifications_read, name='mark-notifications-read'),
    path('ocr-receipt/', csrf_exempt(views.ocr_receipt), name='ocr-receipt'),
    path('recurring-expenses/', views.recurring_expenses, name='recurring_expenses'),
    path('recurring-expenses/add', views.add_recurring, name='add_recurring'),
    path('recurring-expenses/edit/<int:id>', views.edit_recurring, name='edit_recurring'),
    path('recurring-expenses/delete/<int:id>', views.delete_recurring, name='delete_recurring'),
    path('bulk-import/', views.bulk_import_expenses, name='bulk-import-expenses'),
    path('bulk-delete/', views.bulk_delete_expenses, name='bulk-delete-expenses'),
    path('payments/pay/<int:id>/', views.dummy_payment_page, name='dummy_payment'),
    path('payments/confirm/<int:id>/', views.pay_pending_expense, name='pay-pending'),
    path('check-limit-preview/', views.check_limit_preview, name='check-limit-preview'),
]

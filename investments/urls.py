from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path('summary/', views.investment_dashboard, name='investment_dashboard'),
    path('data/', views.investment_data, name='investment_data'),
    path('export/', views.export_investments_csv, name='export_investments_csv'),
    path('', views.investment_list, name='investments'),
    path('add/', views.add_investment, name='add_investment'),
    path('edit/<int:id>/', views.edit_investment, name='edit_investment'),
    path('delete/<int:id>/', views.delete_investment, name='delete_investment'),
    path('search/', csrf_exempt(views.search_investments), name='search_investments'),
    path('bulk-import/', views.bulk_import_investments, name='bulk_import_investments'),
    path('bulk-delete/', views.bulk_delete_investments, name='bulk_delete_investments'),
]

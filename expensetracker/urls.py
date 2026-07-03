from django.contrib import admin
from django.urls import path, include
from savings import views as savings_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('expenses.urls')),
    path('authentication/', include('authentication.urls')),
    path('preferences/', include('userpreferences.urls')),
    path('income/', include('userincome.urls')),
    path('forecast/', include('expense_forecast.urls')),
    path('api/', include('api.urls')),
    path('goals/',include('goals.urls')),
    path('account/',include('userprofile.urls')),
    path('investments/', include('investments.urls')),
    path('savings/dashboard/', savings_views.savings_dashboard, name='savings-dashboard'),
    path('savings/spending-control/save/', savings_views.save_spending_control, name='save-spending-control'),
]

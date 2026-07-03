from django.urls import path
from . import views
urlpatterns = [
    path('', views.forecast, name='forecast'),
    path('accuracy/', views.accuracy, name='accuracy_dashboard'),
    path('retrain/', views.retrain_model_view, name='retrain_model'),
]
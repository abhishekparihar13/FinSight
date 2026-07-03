from django.db import models
from django.contrib.auth.models import User

class Investment(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)        # e.g. "Gold - Growth Strategy"
    investment_type = models.CharField(max_length=50, choices=[
        ('Stocks','Stocks'),('Mutual Fund','Mutual Fund'),
        ('Fixed Deposit','Fixed Deposit'),('Gold','Gold'),
        ('REIT','REIT'),('Crypto','Crypto'),('ETF','ETF'),
        ('Bond','Bond'),('Options','Options'),('Forex','Forex'),('Other','Other')
    ])
    amount_invested = models.DecimalField(max_digits=12, decimal_places=2)
    returns = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date = models.DateField()
    sell_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10)       # "Active" or "Sold"
    notes = models.TextField(blank=True)

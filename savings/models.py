from django.db import models
from django.contrib.auth.models import User

class SpendingControl(models.Model):
    owner = models.OneToOneField(User, on_delete=models.CASCADE)
    allow_overspending = models.BooleanField(default=False)
    required_saving_threshold = models.DecimalField(max_digits=5, decimal_places=1, default=20.0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.owner.username}'s Spending Control"

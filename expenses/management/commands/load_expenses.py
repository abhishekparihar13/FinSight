"""
HOW TO RUN (Windows):
  1. Place this file at:
        major project/expenses/management/commands/load_expenses.py

  2. Place expenses_500.csv at:
        major project/expenses_500.csv   (same folder as manage.py)

  3. Open terminal in the "major project" folder and run:
        python manage.py load_expenses --username YOUR_LOGIN_USERNAME

  Example:
        python manage.py load_expenses --username admin
"""

import os
import datetime
import pandas as pd
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from expenses.models import Expense
from expenses.ml.text_preprocess import preprocess_text
from expenses.ml.model_service import retrain_model


class Command(BaseCommand):
    help = "Load expenses_500.csv into the database and retrain the ML model"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            required=True,
            help="Django username to assign expenses to",
        )

    def handle(self, *args, **options):
        username = options["username"]

        # 1. Get user
        try:
            user = User.objects.get(username=username)
            self.stdout.write(self.style.SUCCESS(f"[OK] Found user: {user.username}"))
        except User.DoesNotExist:
            all_users = list(User.objects.values_list("username", flat=True))
            self.stdout.write(self.style.ERROR(f"[FAIL] User '{username}' not found."))
            self.stdout.write(f"       Available users: {all_users}")
            return

        # 2. Load CSV
        # __file__ = major project/expenses/management/commands/load_expenses.py
        # go up 4 levels to reach "major project/"
        BASE_DIR = os.path.dirname(  # major project/
                    os.path.dirname(  # expenses/
                     os.path.dirname(  # management/
                      os.path.dirname(  # commands/
                       os.path.abspath(__file__)))))
        CSV_PATH = os.path.join(BASE_DIR, "expenses_500.csv")
        DATASET_PATH = os.path.join(BASE_DIR, "expenses", "dataset.csv")

        if not os.path.exists(CSV_PATH):
            self.stdout.write(self.style.ERROR(f"[FAIL] expenses_500.csv not found at: {CSV_PATH}"))
            return

        df = pd.read_csv(CSV_PATH)
        self.stdout.write(self.style.SUCCESS(f"[OK] Loaded CSV with {len(df)} rows"))

        # 3. Insert into DB
        expenses_to_create = []
        skipped = 0

        for _, row in df.iterrows():
            try:
                expense_date = datetime.datetime.strptime(str(row["date"]), "%Y-%m-%d").date()
                expenses_to_create.append(
                    Expense(
                        owner=user,
                        amount=float(row["amount"]),
                        date=expense_date,
                        description=str(row["description"]).strip(),
                        category=str(row["category"]).strip(),
                    )
                )
            except Exception as e:
                skipped += 1
                self.stdout.write(f"  [SKIP] {e}")

        Expense.objects.bulk_create(expenses_to_create)
        self.stdout.write(self.style.SUCCESS(
            f"[OK] Inserted {len(expenses_to_create)} records into DB (skipped: {skipped})"
        ))

        # 4. Update dataset.csv
        existing_dataset = pd.read_csv(DATASET_PATH)
        existing_descriptions = set(existing_dataset["description"].str.lower().str.strip())

        new_rows = []
        for _, row in df.iterrows():
            desc = str(row["description"]).strip()
            cat = str(row["category"]).strip()
            if desc.lower() not in existing_descriptions:
                new_rows.append({
                    "description": desc,
                    "category": cat,
                    "clean_description": preprocess_text(desc),
                })
                existing_descriptions.add(desc.lower())

        if new_rows:
            new_df = pd.DataFrame(new_rows)
            updated = pd.concat([existing_dataset, new_df], ignore_index=True)
            updated.to_csv(DATASET_PATH, index=False)
            self.stdout.write(self.style.SUCCESS(
                f"[OK] Added {len(new_rows)} new rows to dataset.csv (total: {len(updated)})"
            ))
        else:
            self.stdout.write("[--] No new descriptions to add")

        # 5. Retrain ML model
        self.stdout.write("[..] Retraining ML model ...")
        retrain_model()
        self.stdout.write(self.style.SUCCESS("[OK] Model retrained successfully!"))

        self.stdout.write("\n" + "=" * 45)
        self.stdout.write(f"  DB records inserted : {len(expenses_to_create)}")
        self.stdout.write(f"  dataset.csv new rows: {len(new_rows)}")
        self.stdout.write("=" * 45)

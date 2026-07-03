import pandas as pd
import os
from expenses.ml.model_service import retrain_model
from expenses.ml.text_preprocess import preprocess_text

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_PATH = os.path.join(BASE_DIR, "dataset.csv")

def update_dataset(description, category):
    data = pd.read_csv(DATASET_PATH)

    new_row = {
        "description": description,
        "category": category,
        "clean_description": preprocess_text(description)
    }

    data = pd.concat([data, pd.DataFrame([new_row])], ignore_index=True)
    data.to_csv(DATASET_PATH, index=False)

    # Retrain model after updating dataset
    retrain_model()

    return True

def bulk_update_dataset(rows):
    if not rows:
        return False
        
    data = pd.read_csv(DATASET_PATH)
    existing_descriptions = set(data["description"].str.lower().str.strip())
    
    new_rows = []
    for row in rows:
        desc = row['description'].strip()
        cat = row['category'].strip()
        if desc.lower() not in existing_descriptions:
            new_rows.append({
                "description": desc,
                "category": cat,
                "clean_description": preprocess_text(desc)
            })
            existing_descriptions.add(desc.lower())
            
    if new_rows:
        data = pd.concat([data, pd.DataFrame(new_rows)], ignore_index=True)
        data.to_csv(DATASET_PATH, index=False)
        retrain_model()
        return True
    
    return False
import pandas as pd
import os
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from expenses.ml.text_preprocess import preprocess_text
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_PATH = os.path.join(BASE_DIR, "dataset.csv")
MODEL_PATH = os.path.join(BASE_DIR, "ml", "model.pkl")
VECTORIZER_PATH = os.path.join(BASE_DIR, "ml", "vectorizer.pkl")

model = joblib.load(MODEL_PATH)
vectorizer = joblib.load(VECTORIZER_PATH)

def predict_category(description):
    clean_text = preprocess_text(description)
    X = vectorizer.transform([clean_text])
    prediction = model.predict(X)
    return prediction[0]

def retrain_model():
    data = pd.read_csv(DATASET_PATH)

    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(data["clean_description"])
    y = data["category"]

    model = RandomForestClassifier()
    model.fit(X, y)

    joblib.dump(model, MODEL_PATH)
    joblib.dump(vectorizer, VECTORIZER_PATH)

    print("Model retrained successfully.")
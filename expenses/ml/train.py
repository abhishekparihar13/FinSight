import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from expenses.ml.text_preprocess import preprocess_text

data = pd.read_csv("dataset.csv")
data["clean_description"] = data["description"].apply(preprocess_text)

vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(data['clean_description'])
y = data['category']

model = RandomForestClassifier()
model.fit(X, y)

joblib.dump(model, "model.pkl")
joblib.dump(vectorizer, "vectorizer.pkl")

print("Model trained and saved.")
# expenses/ml/text_preprocess.py

from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import nltk

# Download once (safe check)
try:
    stop_words = set(stopwords.words('english'))
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')
    stop_words = set(stopwords.words('english'))


def preprocess_text(text):
    tokens = word_tokenize(text.lower())
    tokens = [t for t in tokens if t.isalnum() and t not in stop_words]
    return " ".join(tokens)
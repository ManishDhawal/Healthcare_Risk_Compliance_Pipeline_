import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
DATA_RAW = os.path.join(BASE_DIR, "data", "raw", "healthcare_dataset.csv")
DATA_PROCESSED = os.path.join(BASE_DIR, "data", "processed", "clean.parquet")

def load_env():
    load_dotenv()
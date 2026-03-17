import os
import pandas as pd
from src.config.settings import DATA_RAW


def test_raw_exists():
    assert os.path.exists(DATA_RAW), "Place the CSV at data/raw/healthcare_dataset.csv"
    
def test_can_read_header():
    df = pd.read_csv(DATA_RAW, nrows=0)
    assert len(df.columns) > 0, "CSV appears to have no columns"
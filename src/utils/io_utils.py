import os
import pandas as pd

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)
    
def read_csv_exact(path: str) -> pd.DataFrame:
    # no fabrication in the data because the data already has real world instances, so load exactly as is
    return pd.read_csv(path)

def write_parquet(df: pd.DataFrame, path: str):
    ensure_dir(os.path.dirname(path))
    df.to_parquet(path, index=False)
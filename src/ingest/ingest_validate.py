import os, sys
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


from src.config.settings import DATA_RAW, DATA_PROCESSED, load_env
from src.utils.io_utils import write_parquet

def main():
    load_env()
    
    df = pd.read_csv(DATA_RAW)
    
    cols = list(df.columns)
    print("COLUMNS:", " | ".join(cols))
    
    
    write_parquet(df, DATA_PROCESSED)
    print(f"Saved processed copy -> {DATA_PROCESSED}")
    print(f"Rows: {len(df):,} Cols: {len(cols)}")
    


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("Make sure your CSV is at data/raw/healthcare_dataset.csv")
        sys.exit(1)
    
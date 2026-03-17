import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd
from sqlalchemy import create_engine, text
from src.config.settings import DATA_PROCESSED, load_env

TABLE = "stg_healthcare_raw"
SCHEMA = "public"


def engine_from_env():
    load_env()
    host = os.getenv("PG_HOST", "localhost")
    port = os.getenv("PG_PORT", "5432")
    db = os.getenv("PG_DB", "healthcare")
    user = os.getenv("PG_USER", "postgres")
    pwd = os.getenv("PG_PASSWORD", "5432")

    if user and (pwd is None or pwd == ""):
        url = f"postgresql+psycopg2://{user}@{host}:{port}/{db}"

    elif user and pwd:
        url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"
    
    else:
        url = f"postgresql+psycopg2://{host}:{port}/{db}"

    return create_engine(url, future=True)

def main():
    df = pd.read_parquet(DATA_PROCESSED)

    eng = engine_from_env()
    with eng.begin() as con:
        con.execute(text(f'DROP TABLE IF EXISTS "{SCHEMA}"."{TABLE}";'))

    df.to_sql(TABLE, eng, schema=SCHEMA, if_exists="fail", index=False, chunksize=10000, method="multi")


    with eng.connect() as con:
        result = con.execute(text(f'SELECT COUNT(*) FROM "{SCHEMA}"."{TABLE}";'))

        cnt = result.scalar_one()
        cnt = int(cnt)
    print(f"Loaded {cnt:,} rows into {SCHEMA}.{TABLE}")

if __name__ =="__main__":
    main()
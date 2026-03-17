import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


import pandas as pd
from sqlalchemy import create_engine, text
from src.config.settings import load_env

def engine_from_env():
    load_env()
    host = os.getenv("PG_HOST", "localhost")
    port = os.getenv("PG_PORT", "5432")
    db   = os.getenv("PG_DB", "healthcare")
    user = os.getenv("PG_USER", "postgres")
    pwd  = os.getenv("PG_PASSWORD", "5432")


    if user and (pwd is None or pwd == ""):
        url = f"postgresql+psycopg2://{user}@{host}:{port}/{db}"
    elif user and pwd:
        url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"
    else:
        url = f"postgresql+psycopg2://{host}:{port}/{db}"
    return create_engine(url, future=True)


def load_staging():
    eng = engine_from_env()

    # find the schema that actually has stg_healthcare
    find_sql = text("""
        select table_schema
        from information_schema.tables
        where table_name = 'stg_healthcare'
          and table_type in ('BASE TABLE','VIEW')
        order by case when table_schema='staging' then 0
                      when table_schema='public'  then 1
                      else 2 end
        limit 1
    """)
    with eng.connect() as con:
        row = con.execute(find_sql).fetchone()
    if not row:
        raise RuntimeError("Could not find stg_healthcare in any schema. Did you run `dbt run`?")

    schema = row[0]
    q = text(f"""
        select
            name,
            age,
            gender,
            blood_type,
            medical_condition,
            date_of_admission,
            discharge_date,
            doctor,
            hospital,
            insurance_provider,
            billing_amount,
            room_number,
            admission_type,
            medication,
            test_results
        from "{schema}".stg_healthcare
    """)
    
    df = pd.read_sql(q,eng)
    return df

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    fe = df.copy()

    # 1) Coerce to pandas datetime64[ns] (works even if they're already datetime)
    fe["date_of_admission"] = pd.to_datetime(fe["date_of_admission"], errors="coerce")
    fe["discharge_date"]    = pd.to_datetime(fe["discharge_date"],    errors="coerce")

    # 2) Length of stay in days (NaN if either date missing)
    fe["los_days"] = (fe["discharge_date"] - fe["date_of_admission"]).dt.days

    # 3) Numeric base
    num = pd.DataFrame({
        "age": pd.to_numeric(fe["age"], errors="coerce"),
        "billing_amount": pd.to_numeric(fe["billing_amount"], errors="coerce"),
        "los_days": pd.to_numeric(fe["los_days"], errors="coerce"),
    })

    # 4) Compact one-hots for a few high-signal categoricals
    cats = fe[["admission_type","medical_condition","insurance_provider"]].astype("category")
    oh = pd.get_dummies(cats, prefix=["adm","cond","ins"], drop_first=True)

    X = pd.concat([num, oh], axis=1)
    X.index.name = "row_id"
    return X, fe

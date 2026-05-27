import os
import sys
from sqlalchemy import create_engine, text

# URLs we gathered from the workspace configuration and the companion project
URLS = {
    "InteractiveLearning_env": "postgresql://postgres.epbyruyoblszmbcgpfvh:TiszaloK123@aws-0-eu-west-1.pooler.supabase.com:6543/postgres",
    "check_db_scratch": "postgresql://postgres.itpivsqitjscfdfswvuy:Kobot20242024@aws-0-eu-central-1.pooler.supabase.com:6543/postgres",
}

def test_conn(name, url):
    print(f"\n--- Testing Connection: {name} ---")
    print(f"URL: {url.split('@')[-1]}") # hide password in logs
    try:
        engine = create_engine(
            url,
            connect_args={"connect_timeout": 5},
            pool_pre_ping=True
        )
        with engine.connect() as conn:
            # Test query
            res = conn.execute(text("SELECT 1")).scalar()
            print(f"  [OK] Connection alive. Test query returned: {res}")
            
            # Check for core tables
            for table in ["diakok", "felhasznalok", "osztalyok", "jelenlet", "kulso_jegyek"]:
                try:
                    count = conn.execute(text(f"SELECT COUNT(*) FROM public.{table}")).scalar()
                    print(f"  [OK] Table 'public.{table}' exists. Rows: {count}")
                except Exception as tbl_err:
                    print(f"  [ERR] Table 'public.{table}' check failed: {tbl_err}")
            
    except Exception as e:
        print(f"  [FAIL] Connection failed: {e}")

if __name__ == "__main__":
    for name, url in URLS.items():
        test_conn(name, url)

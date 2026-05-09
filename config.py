import os
import psycopg2
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
def get_db():
    return psycopg2.connect(
        host=os.getenv("dpg-d7vottbrjlhs73duc5n0-a"),
        database=os.getenv("online_shop_db_ixcd"),
        user=os.getenv("online_shop_db_ixcd_user"),
        password=os.getenv("W8n91glskNtNwqkSD8YDGxcMF1rNBIN7"),
        port=os.getenv("5432")
    )

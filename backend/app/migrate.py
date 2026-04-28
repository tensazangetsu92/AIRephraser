# migrate.py - для создания таблиц
from app.database import create_tables

if __name__ == "__main__":
    print("Creating database tables...")
    create_tables()
    print("Done!")
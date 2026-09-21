"""Canonical database initialization entry point."""

from database.db_service import DatabaseService

def init_db():
        DatabaseService.init_db()
        print(f"Database initialized successfully at: {DatabaseService.DB_NAME}")

if __name__ == '__main__':
    init_db()
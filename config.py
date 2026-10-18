"""Application configuration."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
DATABASE_PATH = os.path.join(BASE_DIR, "library.db")

# Business rules
DAILY_FINE_RATE = 5.0   # Rs. 5 per overdue day (configurable)
LOAN_PERIOD_DAYS = 14   # standard loan period

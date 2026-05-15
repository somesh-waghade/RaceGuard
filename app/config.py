"""
config.py — Application-wide configuration for RaceGuard.

Reads values from environment variables (or .env file via python-dotenv).
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Number of items available at flash-sale start
INITIAL_STOCK: int = int(os.getenv("INITIAL_STOCK", "10"))

# Redis connection URL
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

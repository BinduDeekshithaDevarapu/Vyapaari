import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load environment variables
load_dotenv()

class Settings(BaseSettings):
    # Supabase Configuration
    SUPABASE_URL: str = os.getenv('SUPABASE_URL', '')
    SUPABASE_KEY: str = os.getenv('SUPABASE_KEY', '')
    
    # Twilio Configuration
    TWILIO_ACCOUNT_SID: str = os.getenv('TWILIO_ACCOUNT_SID', '')
    TWILIO_AUTH_TOKEN: str = os.getenv('TWILIO_AUTH_TOKEN', '')
    TWILIO_PHONE_NUMBER: str = os.getenv('TWILIO_PHONE_NUMBER', '')
    
    # Google Cloud Configuration
    GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')
    
    # Application Settings
    DEBUG: bool = os.getenv('DEBUG', 'False').lower() == 'true'
    STOCK_THRESHOLD: int = int(os.getenv('STOCK_THRESHOLD', '2'))
    
    # Database Tables
    PRODUCTS_TABLE: str = 'products'
    CREDITORS_TABLE: str = 'creditors'
    ORDERS_TABLE: str = 'orders'
    TRANSACTIONS_TABLE: str = 'transactions'
    
    class Config:
        env_file = '.env'

# Create settings instance
settings = Settings() 
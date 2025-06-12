from supabase import create_client, Client
from src.config import settings
import logging
from typing import Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        """Initialize Supabase client."""
        try:
            self.client: Client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_KEY
            )
            self.table = self.client.table(settings.PRODUCTS_TABLE)
            logger.info("Successfully connected to Supabase")
        except Exception as e:
            logger.error(f"Failed to connect to Supabase: {str(e)}")
            raise

    def add_product(self, product_data: dict) -> dict:
        """Add a new product."""
        try:
            response = self.table.insert(product_data).execute()
            return response.data[0]
        except Exception as e:
            logger.error(f"Error adding product: {str(e)}")
            raise

    def add_creditor(self, creditor_data: dict) -> dict:
        """Add a new creditor."""
        try:
            response = self.client.table(settings.CREDITORS_TABLE)\
                .insert(creditor_data)\
                .execute()
            return response.data[0]
        except Exception as e:
            logger.error(f"Error adding creditor: {str(e)}")
            raise

    def add_order(self, order_data: dict) -> dict:
        """Add a new order."""
        try:
            response = self.client.table(settings.ORDERS_TABLE)\
                .insert(order_data)\
                .execute()
            return response.data[0]
        except Exception as e:
            logger.error(f"Error adding order: {str(e)}")
            raise

    def add_transaction(self, transaction_data: dict) -> dict:
        """Add a new transaction."""
        try:
            response = self.client.table(settings.TRANSACTIONS_TABLE)\
                .insert(transaction_data)\
                .execute()
            return response.data[0]
        except Exception as e:
            logger.error(f"Error adding transaction: {str(e)}")
            raise

    def get_product_by_barcode(self, barcode: str) -> Optional[dict]:
        """Get product by barcode."""
        try:
            response = self.table.select("*")\
                .eq("barcode", barcode)\
                .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error getting product by barcode: {str(e)}")
            return None

    def get_product_by_name(self, name: str) -> Optional[dict]:
        """Get product by name (case insensitive)."""
        try:
            response = self.table.select("*")\
                .ilike("name", name)\
                .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error getting product by name: {str(e)}")
            return None

    def update_product_price(self, barcode: str, new_price: float) -> dict:
        """Update product price by barcode."""
        try:
            response = self.table.update({"price": new_price})\
                .eq("barcode", barcode)\
                .execute()
            return response.data[0]
        except Exception as e:
            logger.error(f"Error updating product price: {str(e)}")
            raise

    def create_order(self, product_id: str, quantity: int, total_price: float) -> dict:
        """Create a new order."""
        try:
            order_data = {
                "product_id": product_id,
                "quantity": quantity,
                "total_price": total_price,
                "status": "completed",
                "created_at": datetime.utcnow().isoformat()
            }
            response = self.client.table(settings.ORDERS_TABLE)\
                .insert(order_data)\
                .execute()
            return response.data[0]
        except Exception as e:
            logger.error(f"Error creating order: {str(e)}")
            raise

# Create a single instance
db = Database() 
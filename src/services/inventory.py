from ..database import db
from ..config import settings
from .whatsapp import WhatsAppService
import logging
from typing import List, Dict, Optional
import re

logger = logging.getLogger(__name__)

class InventoryService:
    def __init__(self):
        """Initialize services."""
        self.whatsapp = WhatsAppService()

    async def list_products(self) -> str:
        """List all products with their stock levels."""
        try:
            products = await db.get_products()
            if not products:
                return "No products found in inventory."
            
            # Format response
            response = "📦 *Inventory List*\n\n"
            for product in products:
                stock_status = "⚠️" if product['quantity'] <= settings.STOCK_THRESHOLD else "✅"
                response += f"{stock_status} {product['name']}:\n"
                response += f"   • Quantity: {product['quantity']} {product['unit']}\n"
                response += f"   • Price: ₹{product['price']:.2f}\n\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Error listing products: {str(e)}")
            return "Sorry, couldn't fetch the inventory list. Please try again."

    async def get_low_stock(self) -> str:
        """Get list of products with low stock."""
        try:
            products = await db.get_products()
            low_stock = [p for p in products if p['quantity'] <= settings.STOCK_THRESHOLD]
            
            if not low_stock:
                return "No products are low in stock."
            
            # Format response
            response = "⚠️ *Low Stock Alert*\n\n"
            for product in low_stock:
                response += f"• {product['name']}: {product['quantity']} {product['unit']} left\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting low stock: {str(e)}")
            return "Sorry, couldn't fetch low stock items. Please try again."

    async def add_products_manual(self, from_number: str) -> str:
        """Add products manually."""
        try:
            # Store state in database or cache
            await db.add_transaction({
                "type": "add_products_manual",
                "status": "pending",
                "user_phone": from_number
            })
            
            return (
                "Please send product details in this format:\n"
                "product_name quantity price\n\n"
                "Example:\n"
                "milk 10 20\n"
                "bread 5 15\n\n"
                "Type 'end' when done."
            )
            
        except Exception as e:
            logger.error(f"Error starting manual product addition: {str(e)}")
            return "Sorry, couldn't start product addition. Please try again."

    async def add_products_barcode(self, from_number: str) -> str:
        """Add products via barcode."""
        try:
            # Store state in database or cache
            await db.add_transaction({
                "type": "add_products_barcode",
                "status": "pending",
                "user_phone": from_number
            })
            
            return (
                "Please send barcode image followed by quantity and price.\n"
                "Format after image:\n"
                "quantity price\n\n"
                "Example:\n"
                "10 20\n\n"
                "Type 'end' when done."
            )
            
        except Exception as e:
            logger.error(f"Error starting barcode product addition: {str(e)}")
            return "Sorry, couldn't start product addition. Please try again."

    async def process_barcode_image(self, media_url: str, from_number: str) -> str:
        """Process barcode image and extract product details."""
        try:
            # TODO: Implement barcode scanning using Google Cloud Vision API
            # For now, return a placeholder response
            return (
                "Please send quantity and price for the scanned product.\n"
                "Format:\n"
                "quantity price"
            )
            
        except Exception as e:
            logger.error(f"Error processing barcode image: {str(e)}")
            return "Sorry, couldn't process the barcode. Please try again."

    async def change_price_manual(self, from_number: str) -> str:
        """Change product price manually."""
        try:
            # Store state in database or cache
            await db.add_transaction({
                "type": "change_price_manual",
                "status": "pending",
                "user_phone": from_number
            })
            
            return (
                "Please send product name and new price.\n"
                "Format:\n"
                "product_name -price\n\n"
                "Example:\n"
                "milk -25\n\n"
                "Type 'end' when done."
            )
            
        except Exception as e:
            logger.error(f"Error starting manual price change: {str(e)}")
            return "Sorry, couldn't start price change. Please try again."

    async def change_price_barcode(self, from_number: str) -> str:
        """Change product price via barcode."""
        try:
            # Store state in database or cache
            await db.add_transaction({
                "type": "change_price_barcode",
                "status": "pending",
                "user_phone": from_number
            })
            
            return (
                "Please send barcode image followed by new price.\n"
                "Format after image:\n"
                "-price\n\n"
                "Example:\n"
                "-25\n\n"
                "Type 'end' when done."
            )
            
        except Exception as e:
            logger.error(f"Error starting barcode price change: {str(e)}")
            return "Sorry, couldn't start price change. Please try again."

    async def update_product_quantity(self, product_id: str, quantity: float) -> bool:
        """Update product quantity."""
        try:
            product = await db.get_product_by_name(product_id)
            if not product:
                return False
                
            new_quantity = product['quantity'] + quantity
            if new_quantity < 0:
                return False
                
            await db.update_product(product_id, {"quantity": new_quantity})
            return True
            
        except Exception as e:
            logger.error(f"Error updating product quantity: {str(e)}")
            return False

    async def get_product_by_name(self, name: str) -> Optional[Dict]:
        """Get product by name (case insensitive)."""
        try:
            return await db.get_product_by_name(name)
        except Exception as e:
            logger.error(f"Error getting product by name: {str(e)}")
            return None 
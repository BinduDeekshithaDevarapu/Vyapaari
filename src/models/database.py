import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        """Initialize database connection."""
        # In a real application, this would connect to a database
        # For now, we'll use in-memory storage
        self.products = {}
        self.orders = {}
        self.transactions = {}

    async def add_product(self, name: str, price: float, stock: int, min_quantity: int = 5) -> Dict:
        """Add a new product."""
        product_id = len(self.products) + 1
        product = {
            'id': product_id,
            'name': name,
            'price': price,
            'stock': stock,
            'min_quantity': min_quantity,
            'created_at': datetime.now()
        }
        self.products[product_id] = product
        return product

    async def get_product_by_name(self, name: str) -> Optional[Dict]:
        """Get product by name."""
        for product in self.products.values():
            if product['name'].lower() == name.lower():
                return product
        return None

    async def update_product_price(self, name: str, new_price: float) -> Optional[Dict]:
        """Update product price."""
        product = await self.get_product_by_name(name)
        if product:
            product['price'] = new_price
            return product
        return None

    async def create_order(self, product_id: int, quantity: int, total_price: float) -> Dict:
        """Create a new order."""
        order_id = len(self.orders) + 1
        order = {
            'id': order_id,
            'product_id': product_id,
            'quantity': quantity,
            'total_price': total_price,
            'created_at': datetime.now()
        }
        self.orders[order_id] = order
        return order

    async def get_low_stock_products(self) -> List[Dict]:
        """Get products with low stock."""
        return [
            product for product in self.products.values()
            if product['stock'] <= product['min_quantity']
        ]

    async def list_products(self) -> List[Dict]:
        """List all products."""
        return list(self.products.values()) 
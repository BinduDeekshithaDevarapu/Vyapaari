from src.database import db
import logging
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_connection():
    """Test database connection and basic operations."""
    try:
        # Generate unique phone number for testing
        unique_id = str(uuid.uuid4())[:8]
        test_phone = f"+1{unique_id}"

        # Test products table
        product = {
            "name": f"Test Product {unique_id}",
            "price": 10.99,
            "quantity": 100,
            "min_quantity": 5
        }
        result = db.add_product(product)
        logger.info(f"Added product: {result}")

        # Test creditors table
        creditor = {
            "name": f"Test Customer {unique_id}",
            "phone": test_phone,
            "total_credit": 0
        }
        creditor_result = db.add_creditor(creditor)
        logger.info(f"Added creditor: {creditor_result}")

        # Test orders table
        order = {
            "customer_name": f"Test Customer {unique_id}",
            "customer_phone": test_phone,
            "total_amount": 10.99,
            "status": "completed"
        }
        order_result = db.add_order(order)
        logger.info(f"Added order: {order_result}")

        # Test transactions table
        transaction = {
            "type": "credit",
            "creditor_id": creditor_result["id"],
            "order_id": order_result["id"],
            "amount": 10.99,
            "description": "Test transaction"
        }
        result = db.add_transaction(transaction)
        logger.info(f"Added transaction: {result}")

        logger.info("All database tests passed successfully!")
        
    except Exception as e:
        logger.error(f"Database test failed: {str(e)}")
        raise

if __name__ == "__main__":
    test_connection() 
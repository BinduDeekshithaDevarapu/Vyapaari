from ..database import db
from ..config import settings
from .whatsapp import WhatsAppService
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class CreditService:
    def __init__(self):
        """Initialize services."""
        self.whatsapp = WhatsAppService()

    async def list_creditors(self) -> str:
        """List all creditors and their outstanding amounts."""
        try:
            creditors = await db.get_creditors()
            if not creditors:
                return "No creditors found."
            
            # Format response
            response = "👥 *Creditors List*\n\n"
            for creditor in creditors:
                response += f"• {creditor['name']}:\n"
                response += f"   - Phone: {creditor['phone']}\n"
                response += f"   - Outstanding: ₹{creditor['amount']:.2f}\n"
                response += f"   - Last Updated: {creditor['updated_at']}\n\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Error listing creditors: {str(e)}")
            return "Sorry, couldn't fetch the creditors list. Please try again."

    async def add_creditor(self, from_number: str) -> str:
        """Add new creditor."""
        try:
            # Store state in database or cache
            await db.add_transaction({
                "type": "add_creditor",
                "status": "pending",
                "user_phone": from_number
            })
            
            return (
                "Please send creditor details in this format:\n"
                "name amount -phone\n\n"
                "Example:\n"
                "Rahul 100 -9876543210\n\n"
                "Type 'end' when done."
            )
            
        except Exception as e:
            logger.error(f"Error starting creditor addition: {str(e)}")
            return "Sorry, couldn't start creditor addition. Please try again."

    async def delete_creditor(self, from_number: str) -> str:
        """Delete creditor."""
        try:
            # Store state in database or cache
            await db.add_transaction({
                "type": "delete_creditor",
                "status": "pending",
                "user_phone": from_number
            })
            
            return (
                "Please send creditor details to delete:\n"
                "name -phone\n\n"
                "Example:\n"
                "Rahul -9876543210\n\n"
                "Type 'end' when done."
            )
            
        except Exception as e:
            logger.error(f"Error starting creditor deletion: {str(e)}")
            return "Sorry, couldn't start creditor deletion. Please try again."

    async def process_payment(self, from_number: str) -> str:
        """Process payment from creditor."""
        try:
            # Store state in database or cache
            await db.add_transaction({
                "type": "process_payment",
                "status": "pending",
                "user_phone": from_number
            })
            
            return (
                "Please send payment details in this format:\n"
                "name amount -phone\n\n"
                "Example:\n"
                "Rahul 50 -9876543210\n\n"
                "Type 'end' when done."
            )
            
        except Exception as e:
            logger.error(f"Error starting payment processing: {str(e)}")
            return "Sorry, couldn't start payment processing. Please try again."

    async def get_credit_amount(self, from_number: str) -> str:
        """Get credit amount for a creditor."""
        try:
            # Store state in database or cache
            await db.add_transaction({
                "type": "get_credit_amount",
                "status": "pending",
                "user_phone": from_number
            })
            
            return (
                "Please send creditor details:\n"
                "name -phone\n\n"
                "Example:\n"
                "Rahul -9876543210\n\n"
                "Type 'end' when done."
            )
            
        except Exception as e:
            logger.error(f"Error starting credit amount check: {str(e)}")
            return "Sorry, couldn't start credit amount check. Please try again."

    async def get_total_credit(self) -> str:
        """Get total credit amount."""
        try:
            creditors = await db.get_creditors()
            total = sum(creditor['amount'] for creditor in creditors)
            
            return f"💰 Total Credit Amount: ₹{total:.2f}"
            
        except Exception as e:
            logger.error(f"Error getting total credit: {str(e)}")
            return "Sorry, couldn't fetch total credit amount. Please try again."

    async def update_creditor_amount(self, phone: str, amount: float) -> bool:
        """Update creditor's outstanding amount."""
        try:
            creditor = await db.get_creditor_by_phone(phone)
            if not creditor:
                return False
                
            new_amount = creditor['amount'] + amount
            if new_amount < 0:
                return False
                
            await db.update_creditor(phone, {
                "amount": new_amount,
                "updated_at": datetime.utcnow().isoformat()
            })
            return True
            
        except Exception as e:
            logger.error(f"Error updating creditor amount: {str(e)}")
            return False

    async def get_creditor_by_phone(self, phone: str) -> Optional[Dict]:
        """Get creditor by phone number."""
        try:
            return await db.get_creditor_by_phone(phone)
        except Exception as e:
            logger.error(f"Error getting creditor by phone: {str(e)}")
            return None 
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import re
from ..models.database import Database

logger = logging.getLogger(__name__)

class CreditorHandler:
    def __init__(self, db: Database):
        """Initialize creditor handler."""
        self.db = db
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

    async def start_add_creditor_session(self, user_id: str) -> Dict:
        """Start add creditor session."""
        return {
            'type': 'add_creditor',
            'process_message': self._process_add_creditor_message,
            'end_action': self._end_add_creditor_session
        }

    async def _process_add_creditor_message(self, message: str, session: Dict) -> str:
        """Process message in add creditor session."""
        try:
            # Format: name amount -phone
            phone_match = re.search(r'-(\d{10})', message)
            if not phone_match:
                return "❌ Invalid format. Please use: name amount -phone"

            parts = message[:phone_match.start()].strip().split()
            if len(parts) < 2:
                return "❌ Invalid format. Please use: name amount -phone"

            name = ' '.join(parts[:-1])
            try:
                amount = float(parts[-1])
            except ValueError:
                return "❌ Invalid amount. Please use a number."

            phone = phone_match.group(1)

            # Check if creditor exists
            creditor = await self.db.get_creditor_by_phone(phone)
            if creditor:
                # Update existing creditor
                await self.db.update_creditor_amount(phone, amount)
                return f"✅ Updated credit amount for {name}.\nNew total: ₹{creditor['amount'] + amount}\n\nType 'end' when finished."
            else:
                # Add new creditor
                await self.db.add_creditor(name, phone, amount)
                return f"✅ Added new creditor: {name}\nAmount: ₹{amount}\n\nType 'end' when finished."

        except Exception as e:
            logger.error(f"Error processing add creditor message: {str(e)}")
            return "❌ Error processing message. Please try again."

    async def _end_add_creditor_session(self, session: Dict) -> str:
        """End add creditor session."""
        return "✅ Creditor addition session ended."

    async def start_delete_creditor_session(self, user_id: str) -> Dict:
        """Start delete creditor session."""
        return {
            'type': 'delete_creditor',
            'process_message': self._process_delete_creditor_message,
            'end_action': self._end_delete_creditor_session
        }

    async def _process_delete_creditor_message(self, message: str, session: Dict) -> str:
        """Process message in delete creditor session."""
        try:
            # Format: name -phone
            phone_match = re.search(r'-(\d{10})', message)
            if not phone_match:
                return "❌ Invalid format. Please use: name -phone"

            name = message[:phone_match.start()].strip()
            phone = phone_match.group(1)

            # Check if creditor exists
            creditor = await self.db.get_creditor_by_phone(phone)
            if not creditor:
                return f"❌ Creditor with phone {phone} not found."

            # Delete creditor
            await self.db.delete_creditor(phone)
            return f"✅ Deleted creditor: {name}\n\nType 'end' when finished."

        except Exception as e:
            logger.error(f"Error processing delete creditor message: {str(e)}")
            return "❌ Error processing message. Please try again."

    async def _end_delete_creditor_session(self, session: Dict) -> str:
        """End delete creditor session."""
        return "✅ Creditor deletion session ended."

    async def start_pay_creditor_session(self, user_id: str) -> Dict:
        """Start pay creditor session."""
        return {
            'type': 'pay_creditor',
            'process_message': self._process_pay_creditor_message,
            'end_action': self._end_pay_creditor_session
        }

    async def _process_pay_creditor_message(self, message: str, session: Dict) -> str:
        """Process message in pay creditor session."""
        try:
            # Format: name amount -phone
            phone_match = re.search(r'-(\d{10})', message)
            if not phone_match:
                return "❌ Invalid format. Please use: name amount -phone"

            parts = message[:phone_match.start()].strip().split()
            if len(parts) < 2:
                return "❌ Invalid format. Please use: name amount -phone"

            name = ' '.join(parts[:-1])
            try:
                amount = float(parts[-1])
            except ValueError:
                return "❌ Invalid amount. Please use a number."

            phone = phone_match.group(1)

            # Check if creditor exists
            creditor = await self.db.get_creditor_by_phone(phone)
            if not creditor:
                return f"❌ Creditor with phone {phone} not found."

            # Check if amount is valid
            if amount > creditor['amount']:
                return f"❌ Payment amount (₹{amount}) exceeds credit amount (₹{creditor['amount']})."

            # Update creditor amount
            await self.db.update_creditor_amount(phone, -amount)
            return f"✅ Payment of ₹{amount} recorded for {name}.\nRemaining credit: ₹{creditor['amount'] - amount}\n\nType 'end' when finished."

        except Exception as e:
            logger.error(f"Error processing pay creditor message: {str(e)}")
            return "❌ Error processing message. Please try again."

    async def _end_pay_creditor_session(self, session: Dict) -> str:
        """End pay creditor session."""
        return "✅ Payment session ended."

    async def start_get_credit_amount_session(self, user_id: str) -> Dict:
        """Start get credit amount session."""
        return {
            'type': 'get_credit_amount',
            'process_message': self._process_get_credit_amount_message,
            'end_action': self._end_get_credit_amount_session
        }

    async def _process_get_credit_amount_message(self, message: str, session: Dict) -> str:
        """Process message in get credit amount session."""
        try:
            # Format: name -phone
            phone_match = re.search(r'-(\d{10})', message)
            if not phone_match:
                return "❌ Invalid format. Please use: name -phone"

            name = message[:phone_match.start()].strip()
            phone = phone_match.group(1)

            # Get creditor details
            creditor = await self.db.get_creditor_by_phone(phone)
            if not creditor:
                return f"❌ Creditor with phone {phone} not found."

            # Get transaction history
            transactions = await self.db.get_creditor_transactions(phone)

            # Format response
            response = f"💰 *Credit Details for {name}*\n\n"
            response += f"Current Credit: ₹{creditor['amount']}\n\n"
            
            if transactions:
                response += "*Recent Transactions:*\n"
                for trans in transactions[:5]:  # Show last 5 transactions
                    response += f"• {trans['date']}: ₹{trans['amount']}\n"
            
            response += "\nType 'end' when finished."

            return response

        except Exception as e:
            logger.error(f"Error processing get credit amount message: {str(e)}")
            return "❌ Error processing message. Please try again."

    async def _end_get_credit_amount_session(self, session: Dict) -> str:
        """End get credit amount session."""
        return "✅ Credit amount session ended."

    async def get_total_credit(self) -> str:
        """Get total credit amount."""
        try:
            total = await self.db.get_total_credit()
            return f"💰 *Total Credit Amount: ₹{total}*"
        except Exception as e:
            logger.error(f"Error getting total credit: {str(e)}")
            return "❌ Error getting total credit amount." 
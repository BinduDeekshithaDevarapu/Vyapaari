import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import re
from ..models.database import Database

logger = logging.getLogger(__name__)

class OrderHandler:
    def __init__(self, db: Database):
        """Initialize order handler."""
        self.db = db
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

    async def start_order_manual_session(self, user_id: str) -> Dict:
        """Start manual order session."""
        return {
            'type': 'order_manual',
            'customer': None,
            'items': [],
            'process_message': self._process_order_manual_message,
            'end_action': self._end_order_manual_session
        }

    async def _process_order_manual_message(self, message: str, session: Dict) -> str:
        """Process message in manual order session."""
        try:
            if session['customer'] is None:
                # First message should contain customer details
                # Format: name -phone
                phone_match = re.search(r'-(\d{10})', message)
                if not phone_match:
                    return "❌ Invalid format. Please use: name -phone"

                name = message[:phone_match.start()].strip()
                phone = phone_match.group(1)

                session['customer'] = {
                    'name': name,
                    'phone': phone
                }
                return "✅ Customer details saved. Now enter products (one per line).\nFormat: product_name quantity -price"

            # Process product entry
            # Format: product_name quantity -price
            price_match = re.search(r'-(\d+(?:\.\d+)?)', message)
            if not price_match:
                return "❌ Invalid format. Please use: product_name quantity -price"

            parts = message[:price_match.start()].strip().split()
            if len(parts) < 2:
                return "❌ Invalid format. Please use: product_name quantity -price"

            product_name = ' '.join(parts[:-1])
            try:
                quantity = float(parts[-1])
                price = float(price_match.group(1))
            except ValueError:
                return "❌ Invalid quantity or price. Please use numbers."

            # Check if product exists
            product = await self.db.get_product_by_name(product_name)
            if not product:
                return f"❌ Product '{product_name}' not found."

            # Add to session items
            session['items'].append({
                'product_id': product['id'],
                'name': product_name,
                'quantity': quantity,
                'price': price,
                'total': quantity * price
            })

            return f"✅ Added: {product_name}\nQuantity: {quantity}\nPrice: ₹{price}\nTotal: ₹{quantity * price}\n\nType 'end' when finished."

        except Exception as e:
            logger.error(f"Error processing order manual message: {str(e)}")
            return "❌ Error processing message. Please try again."

    async def _end_order_manual_session(self, session: Dict) -> str:
        """End manual order session."""
        try:
            if not session['items']:
                return "❌ No items in order."

            # Calculate total
            total = sum(item['total'] for item in session['items'])

            # Format response
            response = "📋 *Order Summary*\n\n"
            response += f"Customer: {session['customer']['name']}\n"
            response += f"Phone: {session['customer']['phone']}\n\n"
            
            for item in session['items']:
                response += f"• {item['name']}\n"
                response += f"   Quantity: {item['quantity']}\n"
                response += f"   Price: ₹{item['price']}\n"
                response += f"   Total: ₹{item['total']}\n\n"
            
            response += f"*Total Amount: ₹{total}*"

            # Store order in database
            await self.db.create_order(
                customer_name=session['customer']['name'],
                customer_phone=session['customer']['phone'],
                items=session['items'],
                total=total
            )

            return response

        except Exception as e:
            logger.error(f"Error ending order manual session: {str(e)}")
            return "❌ Error creating order. Please try again."

    async def start_order_barcode_session(self, user_id: str) -> Dict:
        """Start barcode order session."""
        return {
            'type': 'order_barcode',
            'customer': None,
            'current_item': None,
            'items': [],
            'process_message': self._process_order_barcode_message,
            'end_action': self._end_order_barcode_session
        }

    async def _process_order_barcode_message(self, message: str, session: Dict) -> str:
        """Process message in barcode order session."""
        try:
            if session['customer'] is None:
                # First message should contain customer details
                # Format: name -phone
                phone_match = re.search(r'-(\d{10})', message)
                if not phone_match:
                    return "❌ Invalid format. Please use: name -phone"

                name = message[:phone_match.start()].strip()
                phone = phone_match.group(1)

                session['customer'] = {
                    'name': name,
                    'phone': phone
                }
                return "✅ Customer details saved. Now send barcode images."

            if session['current_item'] is None:
                # Expecting quantity
                try:
                    quantity = float(message)
                except ValueError:
                    return "❌ Invalid quantity. Please use a number."

                # Add to session items
                session['items'].append({
                    'product_id': session['barcode_product']['id'],
                    'name': session['barcode_product']['name'],
                    'quantity': quantity,
                    'price': session['barcode_product']['price'],
                    'total': quantity * session['barcode_product']['price']
                })

                session['current_item'] = None
                return f"✅ Added: {session['barcode_product']['name']}\nQuantity: {quantity}\nPrice: ₹{session['barcode_product']['price']}\nTotal: ₹{quantity * session['barcode_product']['price']}\n\nSend next barcode or type 'end'."

            return "❌ Invalid state. Please send a barcode image first."

        except Exception as e:
            logger.error(f"Error processing order barcode message: {str(e)}")
            return "❌ Error processing message. Please try again."

    async def _end_order_barcode_session(self, session: Dict) -> str:
        """End barcode order session."""
        try:
            if not session['items']:
                return "❌ No items in order."

            # Calculate total
            total = sum(item['total'] for item in session['items'])

            # Format response
            response = "📋 *Order Summary*\n\n"
            response += f"Customer: {session['customer']['name']}\n"
            response += f"Phone: {session['customer']['phone']}\n\n"
            
            for item in session['items']:
                response += f"• {item['name']}\n"
                response += f"   Quantity: {item['quantity']}\n"
                response += f"   Price: ₹{item['price']}\n"
                response += f"   Total: ₹{item['total']}\n\n"
            
            response += f"*Total Amount: ₹{total}*\n\n"
            response += "Type 'ok' to confirm or 'no' to cancel."

            # Store order in database
            await self.db.create_order(
                customer_name=session['customer']['name'],
                customer_phone=session['customer']['phone'],
                items=session['items'],
                total=total
            )

            return response

        except Exception as e:
            logger.error(f"Error ending order barcode session: {str(e)}")
            return "❌ Error creating order. Please try again." 
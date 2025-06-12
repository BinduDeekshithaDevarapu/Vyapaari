import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import re
from ..models.database import Database

logger = logging.getLogger(__name__)

class ProductHandler:
    def __init__(self, db: Database):
        """Initialize product handler."""
        self.db = db
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

    async def start_add_manual_session(self, user_id: str) -> Dict:
        """Start manual product addition session."""
        return {
            'type': 'add_manual',
            'products': [],
            'process_message': self._process_add_manual_message,
            'end_action': self._end_add_manual_session
        }

    async def _process_add_manual_message(self, message: str, session: Dict) -> str:
        """Process message in manual product addition session."""
        try:
            # Parse product details
            # Format: product_name quantity price
            parts = message.split()
            if len(parts) < 3:
                return "❌ Invalid format. Please use: product_name quantity price"

            # Extract product details
            product_name = ' '.join(parts[:-2])
            try:
                quantity = float(parts[-2])
                price = float(parts[-1])
            except ValueError:
                return "❌ Invalid quantity or price. Please use numbers."

            # Add to session products
            session['products'].append({
                'name': product_name,
                'quantity': quantity,
                'price': price
            })

            return f"✅ Added: {product_name}\nQuantity: {quantity}\nPrice: ₹{price}\n\nType 'end' when finished."

        except Exception as e:
            logger.error(f"Error processing add manual message: {str(e)}")
            return "❌ Error processing message. Please try again."

    async def _end_add_manual_session(self, session: Dict) -> str:
        """End manual product addition session."""
        try:
            # Add all products to database
            for product in session['products']:
                await self.db.add_product(
                    name=product['name'],
                    quantity=product['quantity'],
                    price=product['price']
                )

            return f"✅ Successfully added {len(session['products'])} products."

        except Exception as e:
            logger.error(f"Error ending add manual session: {str(e)}")
            return "❌ Error adding products. Please try again."

    async def start_add_barcode_session(self, user_id: str) -> Dict:
        """Start barcode product addition session."""
        return {
            'type': 'add_barcode',
            'current_product': None,
            'process_message': self._process_add_barcode_message,
            'end_action': self._end_add_barcode_session
        }

    async def _process_add_barcode_message(self, message: str, session: Dict) -> str:
        """Process message in barcode product addition session."""
        try:
            if session['current_product'] is None:
                # Expecting quantity and price
                parts = message.split()
                if len(parts) != 2:
                    return "❌ Invalid format. Please use: quantity price"

                try:
                    quantity = float(parts[0])
                    price = float(parts[1])
                except ValueError:
                    return "❌ Invalid quantity or price. Please use numbers."

                # Add product to database
                await self.db.add_product(
                    name=session['barcode_name'],
                    quantity=quantity,
                    price=price
                )

                session['current_product'] = None
                return "✅ Product added. Send next barcode or type 'end'."

            return "❌ Invalid state. Please send a barcode image first."

        except Exception as e:
            logger.error(f"Error processing add barcode message: {str(e)}")
            return "❌ Error processing message. Please try again."

    async def _end_add_barcode_session(self, session: Dict) -> str:
        """End barcode product addition session."""
        if session['current_product'] is not None:
            return "❌ Session ended with pending product. Please complete the current product first."
        return "✅ Barcode addition session ended."

    async def start_change_price_manual_session(self, user_id: str) -> Dict:
        """Start manual price change session."""
        return {
            'type': 'change_price_manual',
            'changes': [],
            'process_message': self._process_change_price_manual_message,
            'end_action': self._end_change_price_manual_session
        }

    async def _process_change_price_manual_message(self, message: str, session: Dict) -> str:
        """Process message in manual price change session."""
        try:
            # Parse product and new price
            # Format: product_name new_price
            parts = message.split()
            if len(parts) < 2:
                return "❌ Invalid format. Please use: product_name new_price"

            # Extract details
            product_name = ' '.join(parts[:-1])
            try:
                new_price = float(parts[-1])
            except ValueError:
                return "❌ Invalid price. Please use a number."

            # Check if product exists
            product = await self.db.get_product_by_name(product_name)
            if not product:
                return f"❌ Product '{product_name}' not found. Please add it first."

            # Add to session changes
            session['changes'].append({
                'product_id': product['id'],
                'name': product_name,
                'new_price': new_price
            })

            return f"✅ Price change queued for: {product_name}\nNew price: ₹{new_price}\n\nType 'end' when finished."

        except Exception as e:
            logger.error(f"Error processing change price manual message: {str(e)}")
            return "❌ Error processing message. Please try again."

    async def _end_change_price_manual_session(self, session: Dict) -> str:
        """End manual price change session."""
        try:
            # Apply all price changes
            for change in session['changes']:
                await self.db.update_product_price(
                    product_id=change['product_id'],
                    new_price=change['new_price']
                )

            return f"✅ Successfully updated prices for {len(session['changes'])} products."

        except Exception as e:
            logger.error(f"Error ending change price manual session: {str(e)}")
            return "❌ Error updating prices. Please try again."

    async def start_change_price_barcode_session(self, user_id: str) -> Dict:
        """Start barcode price change session."""
        return {
            'type': 'change_price_barcode',
            'current_product': None,
            'process_message': self._process_change_price_barcode_message,
            'end_action': self._end_change_price_barcode_session
        }

    async def _process_change_price_barcode_message(self, message: str, session: Dict) -> str:
        """Process message in barcode price change session."""
        try:
            if session['current_product'] is None:
                # Expecting new price
                try:
                    new_price = float(message)
                except ValueError:
                    return "❌ Invalid price. Please use a number."

                # Update product price
                await self.db.update_product_price(
                    product_id=session['barcode_product']['id'],
                    new_price=new_price
                )

                session['current_product'] = None
                return "✅ Price updated. Send next barcode or type 'end'."

            return "❌ Invalid state. Please send a barcode image first."

        except Exception as e:
            logger.error(f"Error processing change price barcode message: {str(e)}")
            return "❌ Error processing message. Please try again."

    async def _end_change_price_barcode_session(self, session: Dict) -> str:
        """End barcode price change session."""
        if session['current_product'] is not None:
            return "❌ Session ended with pending product. Please complete the current product first."
        return "✅ Barcode price change session ended." 
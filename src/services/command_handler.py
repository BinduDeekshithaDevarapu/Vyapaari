import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import re
from .voice import VoiceService
from ..models.database import Database

logger = logging.getLogger(__name__)

class CommandHandler:
    def __init__(self, db: Database, voice_service: VoiceService):
        """Initialize command handler."""
        self.db = db
        self.voice = voice_service
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.confirmations: Dict[str, Dict[str, Any]] = {}
        self.pending_confirmations = {}  # Store pending confirmations

    async def handle_command(self, message: str, from_number: str, is_voice: bool = False) -> str:
        """Handle incoming command."""
        try:
            # If it's a voice message, process it first
            if is_voice:
                logger.info(f"Processing voice message from {from_number}")
                # Process voice message using voice service
                result = await self.voice.process_voice_message(message)
                if not result:
                    return "❌ Could not process voice message. Please try again or type your command."
                logger.info(f"Voice message converted to text: {result['text']}")
                message = result['text']

            # Convert message to lowercase for easier matching
            msg = message.lower().strip()

            # Check for active session
            if from_number in self.active_sessions:
                return await self._handle_session_message(msg, from_number)

            # Check for pending confirmation
            if from_number in self.confirmations:
                return await self._handle_confirmation(msg, from_number)

            # Handle different commands
            if msg == 'help':
                return self.voice.get_voice_shortcuts()
            elif msg == 'l':
                return await self._list_products()
            elif msg == 'low':
                return await self._list_low_stock()
            elif msg in ['add new -m', 'add manual', 'add products manually']:
                # Start manual add session
                self.active_sessions[from_number] = {
                    'type': 'manual_add',
                    'handler': self._process_manual_add,
                    'products': []
                }
                return "📝 Enter product details in format:\nproduct_name quantity price\n\nExample:\nmilk 10 20.50\n\nType 'end' when done."
            elif msg in ['add new -b', 'add barcode', 'add products by barcode']:
                # Start barcode add session
                logger.info(f"Starting barcode add session for {from_number}")
                self.active_sessions[from_number] = {
                    'type': 'barcode_add',
                    'handler': self._process_barcode_add,
                    'step': 'waiting_for_barcode'
                }
                return "📷 Send barcode image to add product"
            elif msg in ['add -v', 'add voice', 'add products by voice']:
                # Start voice input session
                self.active_sessions[from_number] = {
                    'type': 'voice_input',
                    'handler': self._process_voice_input
                }
                return "🎤 Send voice message to process"
            elif msg in ['change price -m', 'update price manual', 'modify price manual']:
                # Start manual price change session
                self.active_sessions[from_number] = {
                    'type': 'manual_price',
                    'handler': self._process_manual_price
                }
                return "📝 Enter product name and new price:\nname price"
            elif msg in ['change price -b', 'update price barcode', 'modify price barcode']:
                # Start barcode price change session
                self.active_sessions[from_number] = {
                    'type': 'barcode_price',
                    'handler': self._process_barcode_price
                }
                return "📷 Send barcode image to change price"
            elif msg == 'creditors':
                return await self._list_creditors()
            elif msg in ['add creditor', 'new creditor', 'create creditor']:
                # Start add creditor session
                self.active_sessions[from_number] = {
                    'type': 'add_creditor',
                    'handler': self._process_add_creditor
                }
                return "📝 Enter creditor details:\nname amount phone"
            elif msg in ['del creditor', 'delete creditor', 'remove creditor']:
                # Start delete creditor session
                self.active_sessions[from_number] = {
                    'type': 'delete_creditor',
                    'handler': self._process_delete_creditor
                }
                return "📝 Enter creditor name to delete:"
            elif msg in ['pay', 'pay creditor', 'make payment']:
                # Start payment session
                self.active_sessions[from_number] = {
                    'type': 'payment',
                    'handler': self._process_payment
                }
                return "📝 Enter creditor name and amount:\nname amount"
            elif msg in ['get cred amount', 'check credit', 'view credit']:
                # Start credit check session
                self.active_sessions[from_number] = {
                    'type': 'credit_check',
                    'handler': self._process_credit_check
                }
                return "📝 Enter creditor name:"
            elif msg in ['get total cred', 'total credit', 'all credit']:
                return await self._get_total_credit()
            elif msg in ['daily', 'daily sales', 'today sales']:
                return await self._get_daily_report()
            elif msg in ['weekly', 'weekly sales', 'week sales']:
                return await self._get_weekly_report()
            elif msg in ['total', 'sum', 't']:
                return await self._calculate_total()
            else:
                return "❌ Unknown command. Type 'help' to see available commands."

        except Exception as e:
            logger.error(f"Error handling command: {str(e)}")
            return "❌ An error occurred. Please try again."

    async def _handle_session_message(self, message: str, from_number: str) -> str:
        """Handle message during active session."""
        session = self.active_sessions[from_number]
        handler = session.get('handler')
        
        if not handler:
            return "❌ Invalid session. Please start over."
            
        return await handler(message, from_number)

    async def _process_manual_add(self, message: str, from_number: str) -> str:
        """Process manual product addition."""
        try:
            # Get session
            session = self.active_sessions.get(from_number, {})
            if not session or session.get('type') != 'manual_add':
                return "❌ No active manual add session. Please start with 'add new -m'"

            # Check if user wants to end session
            if message.lower() == 'end':
                if not session.get('products'):
                    return "❌ No products added. Session ended."
                # End session
                del self.active_sessions[from_number]
                return f"✅ Session ended. Added {len(session['products'])} products."

            # Parse product details
            # Format: product_name quantity price
            parts = message.split()
            if len(parts) < 3:
                return "❌ Invalid format. Please use: product_name quantity price\n\nExample:\nmilk 10 20.50\n\nType 'end' when done."

            # Extract product details
            try:
                # Last two parts are quantity and price
                quantity = float(parts[-2])
                price = float(parts[-1])
                # Everything else is the product name
                name = ' '.join(parts[:-2])
            except ValueError:
                return "❌ Invalid quantity or price. Please use numbers.\n\nExample:\nmilk 10 20.50\n\nType 'end' when done."

            # Check if product already exists (case insensitive)
            existing_product = self.db.get_product_by_name(name)
            if existing_product:
                return f"⚠️ Product '{name}' already exists.\n\nSend next product or type 'end' to finish."

            # Add product to session
            if 'products' not in session:
                session['products'] = []
            
            session['products'].append({
                'name': name,
                'quantity': int(quantity),
                'price': price,
                'min_quantity': 5  # Default minimum quantity
            })

            # Add product to database
            try:
                product_data = {
                    "name": name,
                    "price": price,
                    "quantity": int(quantity),
                    "min_quantity": 5
                }
                logger.info(f"Adding product to database: {product_data}")
                result = self.db.add_product(product_data)
                logger.info(f"Product added successfully: {result}")
                
                return f"✅ Added: {name}\nQuantity: {quantity}\nPrice: ₹{price}\n\nSend next product or type 'end' to finish."
            except Exception as e:
                logger.error(f"Error adding product to database: {str(e)}")
                return f"❌ Failed to add product '{name}'. Please try again or type 'end' to finish."

        except Exception as e:
            logger.error(f"Error processing manual add: {str(e)}")
            return "❌ Error processing product addition. Please try again or type 'end' to finish."

    async def _process_barcode_add(self, message: str, from_number: str) -> str:
        """Process barcode product addition."""
        try:
            # Get session
            session = self.active_sessions.get(from_number, {})
            if not session or session.get('type') != 'barcode_add':
                return "❌ No active barcode session. Please start with 'add new -b'"

            # Check session step
            if session.get('step') == 'waiting_for_barcode':
                return "📷 Please send the barcode image\n\nType 'end' when you're done adding products."
            elif session.get('step') == 'waiting_for_details':
                # Parse quantity and price
                try:
                    # Split by '-' to separate quantity and price
                    parts = message.split('-')
                    if len(parts) != 2:
                        return "❌ Invalid format. Please use: quantity-price"
                    
                    quantity = float(parts[0].strip())
                    price = float(parts[1].strip())
                    
                    # Get barcode data
                    barcode_data = session.get('barcode_data', {})
                    if not barcode_data:
                        return "❌ No barcode data found. Please scan barcode again."
                    
                    # Check if product already exists
                    existing_product = self.db.get_product_by_barcode(barcode_data['data'])
                    if existing_product:
                        # Update session state for next product
                        session['step'] = 'waiting_for_barcode'
                        session.pop('barcode_data', None)
                        return f"⚠️ Product with barcode {barcode_data['data']} already exists.\n\nSend next barcode image or type 'end' to finish."
                    
                    # Add product to database
                    product_data = {
                        "name": f"Product-{barcode_data['data']}",  # Use barcode as part of name
                        "price": price,
                        "quantity": int(quantity),  # Convert to int for quantity
                        "barcode": barcode_data['data'],
                        "min_quantity": 5  # Default minimum quantity
                    }
                    logger.info(f"Adding product to database: {product_data}")
                    result = self.db.add_product(product_data)
                    logger.info(f"Product added successfully: {result}")
                    
                    # Update session state for next product
                    session['step'] = 'waiting_for_barcode'
                    session.pop('barcode_data', None)
                    
                    return f"✅ Product added successfully!\nBarcode: {barcode_data['data']}\nPrice: ₹{price}\nQuantity: {quantity}\n\nSend next barcode image or type 'end' to finish."
                    
                except ValueError:
                    return "❌ Invalid quantity or price. Please use numbers."
                except Exception as e:
                    logger.error(f"Error adding product: {str(e)}")
                    return "❌ Failed to add product. Please try again."
            
            return "❌ Invalid session state. Please start over with 'add new -b'"
            
        except Exception as e:
            logger.error(f"Error processing barcode add: {str(e)}")
            return "❌ Error processing barcode addition"

    async def _process_manual_price(self, message: str, from_number: str) -> str:
        """Process manual price change."""
        try:
            # Parse product details
            parts = message.split()
            if len(parts) != 2:
                return "❌ Invalid format. Please use: name price"
                
            name, price = parts
            try:
                price = float(price)
            except ValueError:
                return "❌ Invalid price value."
                
            # Update price
            await self.db.update_product_price(name, price)
            
            # End session
            del self.active_sessions[from_number]
            return f"✅ Price updated for {name}"
            
        except Exception as e:
            logger.error(f"Error updating price: {str(e)}")
            return "❌ Failed to update price."

    async def _process_barcode_price(self, message: str, from_number: str) -> str:
        """Process barcode price change."""
        # This would be handled by the WhatsApp service when receiving media
        return "Processing barcode..."

    async def _process_manual_order(self, message: str, from_number: str) -> str:
        """Process manual order."""
        try:
            # Parse customer details
            parts = message.split()
            if len(parts) != 2:
                return "❌ Invalid format. Please use: name phone"
                
            name, phone = parts
            if not phone.isdigit() or len(phone) != 10:
                return "❌ Invalid phone number."
                
            # Start order
            await self.db.start_order(name, phone)
            
            # Update session
            self.active_sessions[from_number].update({
                'customer': {'name': name, 'phone': phone},
                'handler': self._process_order_items
            })
            return "📝 Enter product and quantity:\nname quantity"
            
        except Exception as e:
            logger.error(f"Error starting order: {str(e)}")
            return "❌ Failed to start order."

    async def _process_order_items(self, message: str, from_number: str) -> str:
        """Process order items."""
        try:
            if message.lower() == 'done':
                # End session and complete order
                session = self.active_sessions[from_number]
                customer = session.get('customer', {})
                del self.active_sessions[from_number]
                return f"✅ Order completed for {customer.get('name', '')}"
                
            # Parse item details
            parts = message.split()
            if len(parts) != 2:
                return "❌ Invalid format. Please use: name quantity"
                
            name, quantity = parts
            try:
                quantity = int(quantity)
            except ValueError:
                return "❌ Invalid quantity."
                
            # Add item to order
            await self.db.add_order_item(name, quantity)
            
            # Ask for more items
            return "✅ Item added. Send more items or 'done' to finish."
            
        except Exception as e:
            logger.error(f"Error adding order item: {str(e)}")
            return "❌ Failed to add item."

    async def _process_barcode_order(self, message: str, from_number: str) -> str:
        """Process barcode order."""
        # This would be handled by the WhatsApp service when receiving media
        return "Processing barcode..."

    async def _process_add_creditor(self, message: str, from_number: str) -> str:
        """Process add creditor."""
        try:
            # Parse creditor details
            parts = message.split()
            if len(parts) != 3:
                return "❌ Invalid format. Please use: name amount phone"
                
            name, amount, phone = parts
            try:
                amount = float(amount)
            except ValueError:
                return "❌ Invalid amount."
                
            if not phone.isdigit() or len(phone) != 10:
                return "❌ Invalid phone number."
                
            # Add creditor
            await self.db.add_creditor(name, amount, phone)
            
            # End session
            del self.active_sessions[from_number]
            return f"✅ Creditor added: {name}"
            
        except Exception as e:
            logger.error(f"Error adding creditor: {str(e)}")
            return "❌ Failed to add creditor."

    async def _process_delete_creditor(self, message: str, from_number: str) -> str:
        """Process delete creditor."""
        try:
            name = message.strip()
            if not name:
                return "❌ Invalid name."
                
            # Delete creditor
            await self.db.delete_creditor(name)
            
            # End session
            del self.active_sessions[from_number]
            return f"✅ Creditor deleted: {name}"
            
        except Exception as e:
            logger.error(f"Error deleting creditor: {str(e)}")
            return "❌ Failed to delete creditor."

    async def _process_payment(self, message: str, from_number: str) -> str:
        """Process payment."""
        try:
            # Parse payment details
            parts = message.split()
            if len(parts) != 2:
                return "❌ Invalid format. Please use: name amount"
                
            name, amount = parts
            try:
                amount = float(amount)
            except ValueError:
                return "❌ Invalid amount."
                
            # Process payment
            await self.db.pay_creditor(name, amount)
            
            # End session
            del self.active_sessions[from_number]
            return f"✅ Payment processed for {name}"
            
        except Exception as e:
            logger.error(f"Error processing payment: {str(e)}")
            return "❌ Failed to process payment."

    async def _process_credit_check(self, message: str, from_number: str) -> str:
        """Process credit check."""
        try:
            name = message.strip()
            if not name:
                return "❌ Invalid name."
                
            # Get credit amount
            amount = await self.db.get_creditor_amount(name)
            
            # End session
            del self.active_sessions[from_number]
            return f"💰 Credit amount for {name}: ₹{amount}"
            
        except Exception as e:
            logger.error(f"Error checking credit: {str(e)}")
            return "❌ Failed to check credit amount."

    async def _process_voice_input(self, message: str, from_number: str) -> str:
        """Process voice input."""
        try:
            # Process voice message using voice service
            result = await self.voice.process_voice_message(message)
            if not result:
                return "❌ Could not process voice message. Please try again or type your message."
            
            # End session
            del self.active_sessions[from_number]
            
            # Process the converted text as a regular command
            return await self.handle_command(result['text'], from_number)
            
        except Exception as e:
            logger.error(f"Error processing voice input: {str(e)}")
            return "❌ Failed to process voice message."

    async def _list_products(self) -> str:
        """List all products."""
        try:
            products = await self.db.get_all_products()
            if not products:
                return "No products found."
                
            response = "📋 Product List:\n\n"
            for product in products:
                response += f"• {product['name']} - ₹{product['price']} (Stock: {product['stock']})\n"
            return response
            
        except Exception as e:
            logger.error(f"Error listing products: {str(e)}")
            return "❌ Failed to list products."

    async def _list_low_stock(self) -> str:
        """List products with low stock."""
        try:
            products = await self.db.get_low_stock_products()
            if not products:
                return "No products with low stock."
                
            response = "⚠️ Low Stock Products:\n\n"
            for product in products:
                response += f"• {product['name']} - {product['stock']} remaining\n"
            return response
            
        except Exception as e:
            logger.error(f"Error listing low stock: {str(e)}")
            return "❌ Failed to list low stock products."

    async def _list_creditors(self) -> str:
        """List all creditors."""
        try:
            creditors = await self.db.get_all_creditors()
            if not creditors:
                return "No creditors found."
                
            response = "📋 Creditor List:\n\n"
            for creditor in creditors:
                response += f"• {creditor['name']} - ₹{creditor['amount']}\n"
            return response
            
        except Exception as e:
            logger.error(f"Error listing creditors: {str(e)}")
            return "❌ Failed to list creditors."

    async def _get_total_credit(self) -> str:
        """Get total credit amount."""
        try:
            total = await self.db.get_total_credit()
            return f"💰 Total credit amount: ₹{total}"
            
        except Exception as e:
            logger.error(f"Error getting total credit: {str(e)}")
            return "❌ Failed to get total credit."

    async def _get_daily_report(self) -> str:
        """Get daily sales report."""
        try:
            report = await self.db.get_daily_report()
            return f"📊 Daily Report:\n{report}"
            
        except Exception as e:
            logger.error(f"Error getting daily report: {str(e)}")
            return "❌ Failed to get daily report."

    async def _get_weekly_report(self) -> str:
        """Get weekly sales report."""
        try:
            report = await self.db.get_weekly_report()
            return f"📊 Weekly Report:\n{report}"
            
        except Exception as e:
            logger.error(f"Error getting weekly report: {str(e)}")
            return "❌ Failed to get weekly report."

    async def _handle_confirmation(self, message: str, from_number: str) -> str:
        """Handle confirmation response."""
        confirmation = self.confirmations[from_number]
        
        if message.lower() in ['yes', 'y', 'confirm']:
            handler = confirmation.get('handler')
            if handler:
                return await handler(confirmation.get('data', {}))
        elif message.lower() in ['no', 'n', 'cancel']:
            return "❌ Operation cancelled."
            
        return "❌ Invalid response. Please answer with yes/no."

    async def _calculate_total(self) -> str:
        """Calculate total sales."""
        try:
            total = await self.db.get_total_sales()
            return f"💰 Total sales: ₹{total}"
            
        except Exception as e:
            logger.error(f"Error calculating total sales: {str(e)}")
            return "❌ Failed to calculate total sales." 
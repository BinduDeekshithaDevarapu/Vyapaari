from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from ..config import settings
import logging
import re
import time
from typing import Dict, Optional
import requests
from io import BytesIO
from PIL import Image
import os
import tempfile
from .barcode import BarcodeService
from .voice import VoiceService
from ..database import db, Database  # Import both the instance and the class
from twilio.request_validator import RequestValidator
from .command_handler import CommandHandler
from .product_handler import ProductHandler
from .order_handler import OrderHandler
from .creditor_handler import CreditorHandler
import json

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self, account_sid: str, auth_token: str, phone_number: str, db: Database):
        """Initialize WhatsApp service."""
        self.client = Client(account_sid, auth_token)
        self.phone_number = phone_number
        self.validator = RequestValidator(auth_token)
        self.db = db  # Use Supabase database instance
        
        # Initialize handlers
        self.voice = VoiceService()
        self.command = CommandHandler(self.db, self.voice)  # Pass both db and voice_service
        self.product = ProductHandler(self.db)
        self.order = OrderHandler(self.db)
        self.creditor = CreditorHandler(self.db)
        self.barcode = BarcodeService()
        
        # Initialize user states
        self.user_states = {}

    def get_help_menu(self) -> str:
        """Get the help menu with all available commands."""
        return (
            "📱 *LocalLedger Help Menu*\n\n"
            "1️⃣ *Inventory Management*\n"
            "   • l - List all products\n"
            "   • low - Show low stock items\n"
            "   • add new -m - Add products manually\n"
            "   • add new -b - Add products via barcode\n"
            "   • change price -m - Change price manually\n"
            "   • change price -b - Change price via barcode\n\n"
            "2️⃣ *Order Management*\n"
            "   • order -m - Create order manually\n"
            "   • order -b - Create order via barcode\n\n"
            "3️⃣ *Credit Management*\n"
            "   • creditors - List all creditors\n"
            "   • add creditor - Add new creditor\n"
            "   • del creditor - Delete creditor\n"
            "   • pay - Process payment\n"
            "   • get cred amount - Check credit amount\n"
            "   • get total cred - Get total credit\n\n"
            "4️⃣ *Reports*\n"
            "   • daily - Daily sales report\n"
            "   • weekly - Weekly sales report\n"
            "   • t - Calculate total\n\n"
            "5️⃣ *Voice Input*\n"
            "   • add -v - Add products via voice\n\n"
            "Type any command to get started!"
        )

    async def handle_message(self, message: Dict) -> str:
        """Handle incoming message."""
        try:
            # Get message type and content
            msg_type = message.get('MediaContentType0')
            from_number = message.get('From', '').replace('whatsapp:', '')
            body = message.get('Body', '').strip()
            
            if not from_number:
                return "❌ Could not determine sender"

            # Handle different message types
            if msg_type and msg_type.startswith('image/'):
                return await self.handle_image(message)
            elif msg_type and msg_type.startswith('audio/'):
                return await self.handle_voice_message(message)
            else:
                # Handle text message
                if not body:
                    return "❌ Empty message"

                # Check if user is in a session
                session = self.command.active_sessions.get(from_number, {})
                if session:
                    # Handle session message
                    if session.get('type') == 'manual_add':
                        return await self.command._process_manual_add(body, from_number)
                    elif session.get('type') == 'barcode_add':
                        if body.lower() == 'end':
                            # End barcode addition session
                            self.command.active_sessions.pop(from_number, None)
                            return "✅ Barcode addition session ended."
                        
                        if session.get('step') == 'waiting_for_details':
                            # Parse quantity and price
                            try:
                                # Split by '-' to separate quantity and price
                                parts = body.split('-')
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
                
                # Handle regular commands
                if body.lower() == 'help':
                    return self.voice.get_voice_shortcuts()
                elif body.lower() == 'l':
                    return await self._list_products()
                elif body.lower() == 'low':
                    return await self._list_low_stock()
                elif body.lower() in ['add new -m', 'add manual', 'add products manually']:
                    # Start manual add session
                    self.command.active_sessions[from_number] = {
                        'type': 'manual_add',
                        'handler': self.command._process_manual_add,
                        'products': []
                    }
                    return "📝 Enter product details in format:\nproduct_name quantity price\n\nExample:\nmilk 10 20.50\n\nType 'end' when done."
                elif body.lower() in ['add new -b', 'add barcode', 'add products by barcode']:
                    # Start barcode add session
                    logger.info(f"Starting barcode add session for {from_number}")
                    self.command.active_sessions[from_number] = {
                        'type': 'barcode_add',
                        'handler': self._process_barcode_add,
                        'step': 'waiting_for_barcode'
                    }
                    return "📷 Send barcode image to add product"
                
                return await self.command.handle_command(body, from_number)

        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            return "❌ Error processing message"

    async def send_message(self, to_number: str, message: str) -> bool:
        """Send WhatsApp message."""
        try:
            self.client.messages.create(
                from_=f'whatsapp:{self.phone_number}',
                body=message,
                to=f'whatsapp:{to_number}'
            )
            return True
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            return False

    def validate_request(self, signature: str, url: str, params: Dict) -> bool:
        """Validate incoming webhook request."""
        return self.validator.validate(url, params, signature)

    def _format_phone_number(self, phone: str) -> str:
        """Format phone number to international format."""
        # Remove any non-digit characters
        phone = re.sub(r'[^0-9+]', '', phone)
        
        # Add + if not present
        if not phone.startswith('+'):
            phone = '+' + phone
            
        # Add country code if not present
        if not phone.startswith('+91'):
            phone = '+91' + phone.lstrip('+')
            
        return phone

    def parse_product_input(self, text: str) -> dict:
        """Parse product input from text."""
        try:
            # Remove any extra spaces and convert to lowercase
            text = ' '.join(text.lower().split())
            
            # Split into parts
            parts = text.split()
            if len(parts) < 3:
                return None
                
            # Get product name (could be multiple words)
            product_parts = []
            i = 0
            while i < len(parts) and not parts[i].replace('.', '').isdigit():
                product_parts.append(parts[i])
                i += 1
                
            if not product_parts:
                return None
                
            product = ' '.join(product_parts)
            
            # Get quantity and price
            if i + 1 >= len(parts):
                return None
                
            try:
                quantity = float(parts[i])
                price = float(parts[i + 1])
                
                return {
                    "name": product,
                    "quantity": quantity,
                    "price": price
                }
            except (ValueError, IndexError):
                return None
                
        except Exception as e:
            logger.error(f"Error parsing product input: {str(e)}")
            return None

    def parse_creditor_input(self, text: str) -> dict:
        """Parse creditor input from text."""
        try:
            # Remove any extra spaces
            text = ' '.join(text.split())
            
            # Split into parts
            parts = text.split()
            if len(parts) < 3:
                return None
                
            # Get name (could be multiple words)
            name_parts = []
            i = 0
            while i < len(parts) and not parts[i].startswith('-'):
                name_parts.append(parts[i])
                i += 1
                
            if not name_parts:
                return None
                
            name = ' '.join(name_parts)
            
            # Get amount and phone
            if i + 1 >= len(parts):
                return None
                
            try:
                amount = float(parts[i].lstrip('-'))
                phone = parts[i + 1].lstrip('-')
                
                return {
                    "name": name,
                    "amount": amount,
                    "phone": phone
                }
            except (ValueError, IndexError):
                return None
                
        except Exception as e:
            logger.error(f"Error parsing creditor input: {str(e)}")
            return None

    def parse_payment_input(self, text: str) -> dict:
        """Parse payment input from text."""
        try:
            # Remove any extra spaces
            text = ' '.join(text.split())
            
            # Split into parts
            parts = text.split()
            if len(parts) < 3:
                return None
                
            # Get name (could be multiple words)
            name_parts = []
            i = 0
            while i < len(parts) and not parts[i].startswith('-'):
                name_parts.append(parts[i])
                i += 1
                
            if not name_parts:
                return None
                
            name = ' '.join(name_parts)
            
            # Get amount and phone
            if i + 1 >= len(parts):
                return None
                
            try:
                amount = float(parts[i].lstrip('-'))
                phone = parts[i + 1].lstrip('-')
                
                return {
                    "name": name,
                    "amount": amount,
                    "phone": phone
                }
            except (ValueError, IndexError):
                return None
                
        except Exception as e:
            logger.error(f"Error parsing payment input: {str(e)}")
            return None

    def parse_order_input(self, text: str) -> dict:
        """Parse order input from text."""
        try:
            # Remove any extra spaces
            text = ' '.join(text.split())
            
            # Split into parts
            parts = text.split()
            if len(parts) < 3:
                return None
                
            # Get product name (could be multiple words)
            product_parts = []
            i = 0
            while i < len(parts) and not parts[i].replace('.', '').isdigit():
                product_parts.append(parts[i])
                i += 1
                
            if not product_parts:
                return None
                
            product = ' '.join(product_parts)
            
            # Get quantity
            if i >= len(parts):
                return None
                
            try:
                quantity = float(parts[i])
                
                return {
                    "product": product,
                    "quantity": quantity
                }
            except ValueError:
                return None
                
        except Exception as e:
            logger.error(f"Error parsing order input: {str(e)}")
            return None

    async def _list_products(self) -> str:
        """List all products."""
        try:
            products = await db.get_products()
            if not products:
                return "No products found."

            response = "📦 *Products List:*\n\n"
            for product in products:
                response += f"• {product['name']}:\n"
                response += f"   - Price: ₹{product['price']:.2f}\n"
                response += f"   - Stock: {product['quantity']}\n"
                if product['barcode']:
                    response += f"   - Barcode: {product['barcode']}\n"
                response += "\n"
            return response
        except Exception as e:
            logger.error(f"Error listing products: {str(e)}")
            return "Sorry, couldn't fetch products. Please try again."

    async def _list_low_stock(self) -> str:
        """List products with low stock."""
        try:
            products = await db.get_products()
            low_stock = [p for p in products if p['quantity'] <= p['min_quantity']]
            
            if not low_stock:
                return "No products with low stock."

            response = "⚠️ *Low Stock Alert:*\n\n"
            for product in low_stock:
                response += f"• {product['name']}:\n"
                response += f"   - Current Stock: {product['quantity']}\n"
                response += f"   - Minimum Required: {product['min_quantity']}\n\n"
            return response
        except Exception as e:
            logger.error(f"Error listing low stock: {str(e)}")
            return "Sorry, couldn't fetch low stock items. Please try again."

    async def _start_manual_add(self) -> str:
        """Start manual product addition process."""
        try:
            # Store state in database
            await db.add_transaction({
                "type": "add_product_manual",
                "status": "pending"
            })
            
            return (
                "Please send product details in the following format:\n"
                "name price quantity min_quantity\n\n"
                "Example:\n"
                "milk 20.50 100 5\n\n"
                "Type 'end' when done."
            )
        except Exception as e:
            logger.error(f"Error starting manual add: {str(e)}")
            return "Sorry, couldn't start product addition. Please try again."

    async def _start_barcode_add(self) -> str:
        """Start barcode product addition process."""
        try:
            # Initialize state
            self.user_states[message['from']] = {
                'action': 'add_product',
                'step': 'waiting_for_barcode'
            }
            
            return (
                "Please send a photo of the product barcode.\n"
                "Then send the price, quantity, and minimum quantity:\n"
                "price quantity min_quantity\n\n"
                "Example:\n"
                "20.50 100 5\n\n"
                "Type 'end' when done."
            )
        except Exception as e:
            logger.error(f"Error starting barcode add: {str(e)}")
            return "Sorry, couldn't start barcode addition. Please try again."

    async def _start_manual_price_change(self) -> str:
        """Start manual price change process."""
        try:
            # Store state in database
            await db.add_transaction({
                "type": "change_price_manual",
                "status": "pending"
            })
            
            return (
                "Please send product name and new price:\n"
                "name price\n\n"
                "Example:\n"
                "milk 25.50\n\n"
                "Type 'end' when done."
            )
        except Exception as e:
            logger.error(f"Error starting manual price change: {str(e)}")
            return "Sorry, couldn't start price change. Please try again."

    async def _start_barcode_price_change(self) -> str:
        """Start barcode price change process."""
        try:
            # Initialize state
            self.user_states[message['from']] = {
                'action': 'change_price',
                'step': 'waiting_for_barcode'
            }
            
            return (
                "Please send a photo of the product barcode.\n"
                "Then send the new price:\n"
                "price\n\n"
                "Example:\n"
                "25.50\n\n"
                "Type 'end' when done."
            )
        except Exception as e:
            logger.error(f"Error starting barcode price change: {str(e)}")
            return "Sorry, couldn't start price change. Please try again."

    async def _start_manual_order(self) -> str:
        """Start manual order process."""
        try:
            # Store state in database
            await db.add_transaction({
                "type": "process_manual_order",
                "status": "pending"
            })
            
            return (
                "Please send customer details first:\n"
                "name -phone\n\n"
                "Then send product details one by one:\n"
                "product_name quantity\n\n"
                "Example:\n"
                "milk 2\n"
                "bread 1\n\n"
                "Type 'end' when done."
            )
        except Exception as e:
            logger.error(f"Error starting manual order: {str(e)}")
            return "Sorry, couldn't start order processing. Please try again."

    async def _start_barcode_order(self) -> str:
        """Start barcode order process."""
        try:
            # Initialize state
            self.user_states[message['from']] = {
                'action': 'order',
                'step': 'waiting_for_customer'
            }
            
            return (
                "Please send customer details first:\n"
                "name -phone\n\n"
                "Then send barcode images one by one, followed by quantity.\n"
                "Type 'end' when done."
            )
        except Exception as e:
            logger.error(f"Error starting barcode order: {str(e)}")
            return "Sorry, couldn't start order processing. Please try again."

    async def _list_creditors(self) -> str:
        """List all creditors."""
        try:
            creditors = await db.get_creditors()
            if not creditors:
                return "No creditors found."

            response = "💳 *Creditors List:*\n\n"
            for creditor in creditors:
                response += f"• {creditor['name']}:\n"
                response += f"   - Phone: {creditor['phone']}\n"
                response += f"   - Credit: ₹{creditor['total_credit']:.2f}\n\n"
            return response
        except Exception as e:
            logger.error(f"Error listing creditors: {str(e)}")
            return "Sorry, couldn't fetch creditors. Please try again."

    async def _start_add_creditor(self) -> str:
        """Start add creditor process."""
        try:
            # Store state in database
            await db.add_transaction({
                "type": "add_creditor",
                "status": "pending"
            })
            
            return (
                "Please send creditor details:\n"
                "name -phone\n\n"
                "Example:\n"
                "John Doe -+1234567890"
            )
        except Exception as e:
            logger.error(f"Error starting add creditor: {str(e)}")
            return "Sorry, couldn't start creditor addition. Please try again."

    async def _start_delete_creditor(self) -> str:
        """Start delete creditor process."""
        try:
            # Store state in database
            await db.add_transaction({
                "type": "delete_creditor",
                "status": "pending"
            })
            
            return (
                "Please send creditor phone number to delete:\n"
                "+1234567890"
            )
        except Exception as e:
            logger.error(f"Error starting delete creditor: {str(e)}")
            return "Sorry, couldn't start creditor deletion. Please try again."

    async def _start_payment(self) -> str:
        """Start payment process."""
        try:
            # Store state in database
            await db.add_transaction({
                "type": "process_payment",
                "status": "pending"
            })
            
            return (
                "Please send payment details:\n"
                "phone amount\n\n"
                "Example:\n"
                "+1234567890 100.50"
            )
        except Exception as e:
            logger.error(f"Error starting payment: {str(e)}")
            return "Sorry, couldn't start payment process. Please try again."

    async def _start_credit_check(self) -> str:
        """Start credit amount check process."""
        try:
            # Store state in database
            await db.add_transaction({
                "type": "check_credit",
                "status": "pending"
            })
            
            return (
                "Please send creditor phone number:\n"
                "+1234567890"
            )
        except Exception as e:
            logger.error(f"Error starting credit check: {str(e)}")
            return "Sorry, couldn't start credit check. Please try again."

    async def _get_total_credit(self) -> str:
        """Get total credit amount."""
        try:
            creditors = await db.get_creditors()
            total = sum(creditor['total_credit'] for creditor in creditors)
            
            response = "💳 *Total Credit:*\n\n"
            response += f"Total Amount: ₹{total:.2f}\n\n"
            
            if creditors:
                response += "Breakdown:\n"
                for creditor in creditors:
                    response += f"• {creditor['name']}: ₹{creditor['total_credit']:.2f}\n"
            
            return response
        except Exception as e:
            logger.error(f"Error getting total credit: {str(e)}")
            return "Sorry, couldn't fetch total credit. Please try again."

    async def _get_daily_report(self) -> str:
        """Get daily sales report."""
        try:
            today = datetime.now().date()
            orders = await db.get_orders_by_date(today)
            
            if not orders:
                return "No sales today."

            total_sales = sum(order['total_amount'] for order in orders)
            
            response = "📊 *Daily Sales Report:*\n\n"
            response += f"Date: {today.strftime('%Y-%m-%d')}\n"
            response += f"Total Sales: ₹{total_sales:.2f}\n"
            response += f"Number of Orders: {len(orders)}\n\n"
            
            response += "Orders:\n"
            for order in orders:
                response += f"• {order['customer_name']}:\n"
                response += f"   - Amount: ₹{order['total_amount']:.2f}\n"
                response += f"   - Time: {order['created_at'].strftime('%H:%M')}\n\n"
            
            return response
        except Exception as e:
            logger.error(f"Error getting daily report: {str(e)}")
            return "Sorry, couldn't fetch daily report. Please try again."

    async def _get_weekly_report(self) -> str:
        """Get weekly sales report."""
        try:
            today = datetime.now().date()
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            
            orders = await db.get_orders_by_date_range(week_start, week_end)
            
            if not orders:
                return "No sales this week."

            total_sales = sum(order['total_amount'] for order in orders)
            
            response = "📊 *Weekly Sales Report:*\n\n"
            response += f"Period: {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}\n"
            response += f"Total Sales: ₹{total_sales:.2f}\n"
            response += f"Number of Orders: {len(orders)}\n\n"
            
            # Group orders by date
            orders_by_date = {}
            for order in orders:
                date = order['created_at'].date()
                if date not in orders_by_date:
                    orders_by_date[date] = []
                orders_by_date[date].append(order)
            
            response += "Daily Breakdown:\n"
            for date, daily_orders in sorted(orders_by_date.items()):
                daily_total = sum(order['total_amount'] for order in daily_orders)
                response += f"• {date.strftime('%Y-%m-%d')}:\n"
                response += f"   - Sales: ₹{daily_total:.2f}\n"
                response += f"   - Orders: {len(daily_orders)}\n\n"
            
            return response
        except Exception as e:
            logger.error(f"Error getting weekly report: {str(e)}")
            return "Sorry, couldn't fetch weekly report. Please try again."

    async def _calculate_total(self) -> str:
        """Calculate total from a list of items."""
        try:
            # Parse items from message
            items = message.split('\n')
            total = 0
            response = "🧮 *Total Calculation:*\n\n"
            
            for item in items:
                if not item.strip():
                    continue
                    
                try:
                    name, price = item.split()
                    price = float(price)
                    total += price
                    response += f"• {name}: ₹{price:.2f}\n"
                except ValueError:
                    continue
            
            response += f"\n*Total: ₹{total:.2f}*"
            return response
        except Exception as e:
            logger.error(f"Error calculating total: {str(e)}")
            return "Sorry, couldn't calculate total. Please try again."

    async def _start_voice_input(self) -> str:
        """Start voice input process."""
        try:
            # Initialize state
            self.user_states[message['from']] = {
                'action': 'voice_input',
                'step': 'waiting_for_voice'
            }
            
            # Get voice shortcuts
            shortcuts = self.voice.get_voice_shortcuts()
            
            return (
                "🎤 *Voice Input Mode*\n\n"
                "You can now send voice messages for:\n"
                "• Adding products\n"
                "• Changing prices\n"
                "• Processing orders\n"
                "• Checking inventory\n\n"
                f"{shortcuts}\n\n"
                "Example commands:\n"
                "• 'add milk 20.50 100'\n"
                "• 'change price of bread to 15'\n"
                "• 'order 2 packets of milk'\n\n"
                "Type 'end' to exit voice mode."
            )
        except Exception as e:
            logger.error(f"Error starting voice input: {str(e)}")
            return "Sorry, couldn't start voice input. Please try again."

    async def handle_image(self, message: Dict) -> str:
        """Handle image message."""
        try:
            # Get image URL from message
            media_url = message.get('MediaUrl0')
            if not media_url:
                logger.error("No MediaUrl0 found in message")
                return "❌ No image found in message"

            # Get user state
            from_number = message.get('From', '').replace('whatsapp:', '')
            if not from_number:
                logger.error("No From field found in message")
                return "❌ Could not determine sender"

            logger.info(f"Processing image from {from_number}")
            
            # Check if user is in a barcode session
            session = self.command.active_sessions.get(from_number, {})
            if session.get('type') != 'barcode_add':
                return "❌ Please start barcode addition with 'add new -b' command first"

            # Process barcode
            logger.info(f"Processing barcode image from {from_number}")
            result = await self.barcode.process_barcode(media_url)
            if not result:
                logger.error("Failed to process barcode")
                return "❌ Could not process barcode. Please try again."

            # Format response
            response = self.barcode.format_barcode_response(result)
            
            # Update session state
            session['barcode_data'] = result
            session['step'] = 'waiting_for_details'
            response += "\n\nPlease send quantity and price in format:\nquantity-price\n\nExample:\n10-20.50"
            
            return response

        except Exception as e:
            logger.error(f"Error handling image: {str(e)}")
            return "❌ Error processing image"

    async def handle_voice_message(self, message: Dict) -> str:
        """Handle incoming voice message."""
        try:
            # Get media URL
            media_url = message.get('MediaUrl0')
            if not media_url:
                return "❌ No media URL found in message."

            # Get sender's phone number
            from_number = message.get('From', '').replace('whatsapp:', '')
            if not from_number:
                return "❌ Could not determine sender."

            # Process voice message
            return await self.command.handle_command(media_url, from_number, is_voice=True)

        except Exception as e:
            logger.error(f"Error handling voice message: {str(e)}")
            return "❌ Failed to process voice message. Please try again or type your command." 
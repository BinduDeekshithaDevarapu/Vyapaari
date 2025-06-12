from ..database import db
from ..config import settings
from .whatsapp import WhatsAppService
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import pandas as pd
from fpdf import FPDF

logger = logging.getLogger(__name__)

class ReportsService:
    def __init__(self):
        """Initialize services."""
        self.whatsapp = WhatsAppService()

    async def get_daily_report(self) -> str:
        """Get daily sales report."""
        try:
            # Get today's date
            today = datetime.utcnow().date()
            
            # Get today's orders
            orders = await db.client.table(settings.ORDERS_TABLE)\
                .select("*")\
                .gte('created_at', today.isoformat())\
                .lt('created_at', (today + timedelta(days=1)).isoformat())\
                .execute()
            
            if not orders.data:
                return "No sales recorded for today."
            
            # Calculate totals
            total_sales = sum(order['total_amount'] for order in orders.data)
            total_items = sum(order['quantity'] for order in orders.data)
            
            # Group by product
            product_sales = {}
            for order in orders.data:
                product = order['product_name']
                if product not in product_sales:
                    product_sales[product] = {
                        'quantity': 0,
                        'amount': 0
                    }
                product_sales[product]['quantity'] += order['quantity']
                product_sales[product]['amount'] += order['total_amount']
            
            # Format response
            response = f"📊 *Daily Report ({today.strftime('%d %b %Y')})*\n\n"
            response += f"Total Sales: ₹{total_sales:.2f}\n"
            response += f"Total Items Sold: {total_items}\n\n"
            response += "*Product-wise Sales:*\n"
            
            for product, sales in product_sales.items():
                response += f"• {product}:\n"
                response += f"   - Quantity: {sales['quantity']}\n"
                response += f"   - Amount: ₹{sales['amount']:.2f}\n\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating daily report: {str(e)}")
            return "Sorry, couldn't generate daily report. Please try again."

    async def get_weekly_report(self) -> str:
        """Get weekly sales report."""
        try:
            # Get date range
            today = datetime.utcnow().date()
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            
            # Get week's orders
            orders = await db.client.table(settings.ORDERS_TABLE)\
                .select("*")\
                .gte('created_at', week_start.isoformat())\
                .lt('created_at', (week_end + timedelta(days=1)).isoformat())\
                .execute()
            
            if not orders.data:
                return "No sales recorded for this week."
            
            # Calculate totals
            total_sales = sum(order['total_amount'] for order in orders.data)
            total_items = sum(order['quantity'] for order in orders.data)
            
            # Group by product
            product_sales = {}
            for order in orders.data:
                product = order['product_name']
                if product not in product_sales:
                    product_sales[product] = {
                        'quantity': 0,
                        'amount': 0
                    }
                product_sales[product]['quantity'] += order['quantity']
                product_sales[product]['amount'] += order['total_amount']
            
            # Format response
            response = f"📈 *Weekly Report ({week_start.strftime('%d %b')} - {week_end.strftime('%d %b %Y')})*\n\n"
            response += f"Total Sales: ₹{total_sales:.2f}\n"
            response += f"Total Items Sold: {total_items}\n\n"
            response += "*Product-wise Sales:*\n"
            
            for product, sales in product_sales.items():
                response += f"• {product}:\n"
                response += f"   - Quantity: {sales['quantity']}\n"
                response += f"   - Amount: ₹{sales['amount']:.2f}\n\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating weekly report: {str(e)}")
            return "Sorry, couldn't generate weekly report. Please try again."

    async def calculate_total(self, text: str) -> str:
        """Calculate total from space-separated numbers."""
        try:
            # Remove command and split numbers
            numbers = text.replace('t', '').strip().split()
            
            # Convert to float and calculate total
            total = sum(float(num) for num in numbers)
            
            return f"Total: ₹{total:.2f}"
            
        except ValueError:
            return "Please enter valid numbers separated by spaces."
        except Exception as e:
            logger.error(f"Error calculating total: {str(e)}")
            return "Sorry, couldn't calculate total. Please try again."

    async def generate_pdf_report(self, report_type: str, data: Dict) -> bytes:
        """Generate PDF report."""
        try:
            pdf = FPDF()
            pdf.add_page()
            
            # Add title
            pdf.set_font('Arial', 'B', 16)
            pdf.cell(0, 10, f'{report_type.capitalize()} Report', 0, 1, 'C')
            
            # Add date
            pdf.set_font('Arial', '', 12)
            pdf.cell(0, 10, f'Generated on: {datetime.utcnow().strftime("%d %b %Y %H:%M")}', 0, 1, 'C')
            
            # Add content
            pdf.set_font('Arial', '', 12)
            for key, value in data.items():
                pdf.cell(0, 10, f'{key}: {value}', 0, 1)
            
            return pdf.output(dest='S').encode('latin1')
            
        except Exception as e:
            logger.error(f"Error generating PDF report: {str(e)}")
            raise 
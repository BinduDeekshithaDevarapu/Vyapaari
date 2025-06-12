from fastapi import FastAPI, Request, Response
from src.services.whatsapp import WhatsAppService
from src.database import db
import logging
import os
from twilio.twiml.messaging_response import MessagingResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Initialize WhatsApp service
whatsapp = WhatsAppService(
    account_sid=os.getenv('TWILIO_ACCOUNT_SID'),
    auth_token=os.getenv('TWILIO_AUTH_TOKEN'),
    phone_number=os.getenv('TWILIO_PHONE_NUMBER'),
    db=db
)

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Welcome to LocalLedger API"}

@app.post("/webhook")
async def webhook(request: Request) -> Response:
    """Handle incoming WhatsApp messages."""
    try:
        # Get form data
        form_data = await request.form()
        logger.info(f"Received webhook data: {dict(form_data)}")
        
        # Create message dict
        message = {
            'From': form_data.get('From'),
            'Body': form_data.get('Body'),
            'MediaContentType0': form_data.get('MediaContentType0'),
            'MediaUrl0': form_data.get('MediaUrl0'),
            'NumMedia': form_data.get('NumMedia')
        }
        
        # Process message
        response_text = await whatsapp.handle_message(message)
        logger.info(f"Sending response: {response_text}")
        
        # Create TwiML response
        resp = MessagingResponse()
        resp.message(response_text)
        
        # Return response with proper headers
        return Response(
            content=str(resp),
            media_type='application/xml',
            headers={
                'Content-Type': 'application/xml',
                'Cache-Control': 'no-cache'
            }
        )
        
    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}")
        resp = MessagingResponse()
        resp.message("❌ An error occurred. Please try again.")
        return Response(
            content=str(resp),
            media_type='application/xml',
            headers={
                'Content-Type': 'application/xml',
                'Cache-Control': 'no-cache'
            }
        )

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
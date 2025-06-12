# LocalLedger - WhatsApp-based Business Management System

LocalLedger is a WhatsApp-based business management system designed for small shop owners in India. It helps them manage inventory, track credit, and generate reports - all through WhatsApp.

## Features

- 📦 Inventory Management
  - Add products manually or via barcode
  - Track stock levels
  - Get low stock alerts
  - Change prices

- 💳 Credit Management
  - Track customer credit
  - Process payments
  - Send payment reminders
  - View credit history

- 📊 Reports
  - Daily sales report
  - Weekly sales report
  - Product-wise sales analysis
  - Total credit amount

- 🎤 Voice Input
  - Add products using voice messages
  - Supports multiple languages
  - Automatic translation to English

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/localledger.git
cd localledger
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Linux/Mac
.\venv\Scripts\activate   # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file with your credentials:
```
# Supabase Configuration
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# Twilio Configuration
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=your_twilio_phone_number

# Google Cloud Configuration
GOOGLE_APPLICATION_CREDENTIALS=path_to_your_credentials.json

# Application Settings
DEBUG=True
STOCK_THRESHOLD=2
```

5. Set up Supabase database:
   - Create tables: products, creditors, orders, transactions
   - Set up appropriate indexes and constraints

6. Run the application:
```bash
uvicorn src.main:app --reload
```

## Usage

1. Send a message to your Twilio WhatsApp number
2. Use the following commands:

### Inventory Management
- `l` - List all products
- `low` - Show low stock items
- `add new -m` - Add products manually
- `add new -b` - Add products via barcode
- `change price -m` - Change price manually
- `change price -b` - Change price via barcode

### Order Management
- `order -m` - Create order manually
- `order -b` - Create order via barcode

### Credit Management
- `creditors` - List all creditors
- `add creditor` - Add new creditor
- `del creditor` - Delete creditor
- `pay` - Process payment
- `get cred amount` - Check credit amount
- `get total cred` - Get total credit

### Reports
- `daily` - Daily sales report
- `weekly` - Weekly sales report
- `t` - Calculate total

### Voice Input
- `add -v` - Add products via voice

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Twilio for WhatsApp integration
- Supabase for database
- Google Cloud for speech-to-text and translation 
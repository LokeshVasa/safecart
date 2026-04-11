# SafeCart – Secure QR-Based Delivery System

SafeCart is a privacy-focused and secure delivery system designed to ensure that packages are delivered only to authorized recipients using multi-layer authentication.

The system integrates:
- Encrypted QR Codes – Securely store delivery information
- Geolocation Validation – Ensures delivery at the correct location
- OTP-Based Authentication – Confirms recipient identity

## Objective
To build a tamper-resistant and fraud-proof delivery mechanism that prevents:
- Unauthorized package access
- Fake or failed deliveries
- Location spoofing attacks

This system enhances trust, security, and efficiency in modern e-commerce logistics.

## Highlights (Current Build)
- QR scan assignment with expiry and scan limits
- Split OTP verification (customer + agent)
- Delivery agent and customer tracking views
- Admin security logs with metrics and charts
- Delivery mode comparison (Secure vs Traditional)
- Simulation tools for research/demo reporting

## Roles
- **Customer**: shops, pays, confirms delivery via Safe Handshake
- **Seller**: prints QR labels and tracks order status
- **Delivery Agent**: scans QR, navigates, completes delivery
- **Admin**: manages roles, reviews security logs, compares delivery modes

## Delivery Modes
- **Secure**: QR + OTP verification required
- **Traditional**: no OTP required; agent can mark delivered directly

Admin can switch delivery mode on the seller orders page. Switching back to Secure resets QR state and assignment so the secure flow restarts cleanly.

## Admin Tools
- **Security Logs**: `/dashboard/admin/security-logs/`
- **Delivery Mode Comparison**: shown on the Admin dashboard

## Project Setup
Follow these steps to run the project locally:

1. Clone the Repository
```bash
git clone https://github.com/LokeshVasa/safecart.git
cd safecart
```

2. Create and activate a virtual environment
```bash
python -m venv venv
```

3. Install Dependencies
```bash
pip install -r requirements.txt
```

4. Configure Database
Update your `settings.py` with PostgreSQL details:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'your_db_name',
        'USER': 'your_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

5. Apply Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

6. Run the Server
```bash
python manage.py runserver
```

Open in browser: `http://127.0.0.1:8000/`

## Simulation Commands 
List available buyers and delivery agents:
```bash
python manage.py list_delivery_users
```

Ensure a buyer has a confirmed address:
```bash
python manage.py ensure_confirmed_address --buyer-username <buyer_username> --street "Demo Street 9" --city "Hyderabad" --state "Telangana" --pincode 500001
```

Run the delivery flow simulation:
```bash
python manage.py simulate_delivery_flows --buyer-username <buyer_username> --agent-username <agent_username> --orders 20 --secure-ratio 0.7 --delivered-ratio 0.8 --attack-ratio 0.3
```

The simulator prints:
- Secure vs Traditional counts
- Delivery success rate
- Attack attempts simulated
- QR/OTP blocked and failed event totals

## Important Notes
- Default delivery mode is **Secure** for new orders.
- Traditional orders skip OTP and allow direct delivery confirmation by the agent.
- Security events are logged with timing metrics for analysis

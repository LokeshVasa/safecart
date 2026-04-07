# 📦 SafeCart – Secure QR-Based Delivery System

SafeCart is a **privacy-focused and secure delivery system** designed to ensure that packages are delivered only to authorized recipients using multi-layer authentication.

The system integrates:

- 🔐 **Encrypted QR Codes** – Securely store delivery information  
- 📍 **Geolocation Validation** – Ensures delivery at the correct location  
- 🔑 **OTP-Based Authentication** – Confirms recipient identity  

### 🎯 Objective

To build a **tamper-resistant and fraud-proof delivery mechanism** that prevents:

- Unauthorized package access  
- Fake or failed deliveries  
- Location spoofing attacks  

This system enhances trust, security, and efficiency in modern e-commerce logistics.

---

## ⚙️ Project Setup

Follow these steps to run the project locally:

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/LokeshVasa/safecart.git
cd safecart
```
### 2️⃣ Create and activate a virtual environment
```bash
python -m venv venv
```
### 3️⃣ Install Dependencies
```bash
pip install -r requirements.txt
```
### 4️⃣ Configure Database
Update your settings.py with PostgreSQL details:
```bash
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
### 5️⃣ Apply Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```
### 6️⃣ Run the Server
```bash
python manage.py runserver
```
Open in browser: http://127.0.0.1:8000/

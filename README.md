# BUSGO — Online Bus Ticket Booking System

A complete, production-style bus ticket booking website built with **Django 5**, **MySQL (XAMPP/MariaDB)**, **Bootstrap 5**, and a custom operations dashboard.

> **BUSGO** — *Your Journey, Our Priority.*

---

## ✨ What's included

| Area | Highlights |
| --- | --- |
| **Homepage** | Hero search (from / to / date), popular routes, featured buses, offers, reviews, "why choose us", how-it-works, newsletter |
| **Authentication** | Register, email-or-username login, show/hide password, remember me, forgot password, profile editing, logout |
| **Search** | Live schedule search with filters for operator, bus type, AC, departure slot, price, availability and sorting |
| **Seat booking** | Interactive seat map (seater 2+2 and sleeper 2+1 lower/upper decks), colour-coded availability, 15-minute server-side seat holds |
| **Passengers** | Contact details + one passenger form per seat, validation, fare breakdown with convenience fee and GST |
| **Payments** | UPI, Google Pay, PhonePe, Paytm, QR, debit/credit card, net banking — clearly labelled **simulated gateway** by default, optional Razorpay test mode |
| **Tickets** | Unique ticket number, QR code, printable e-ticket, downloadable PDF (ReportLab), public ticket verification |
| **My bookings** | Upcoming / completed / cancelled / pending tabs, cancellation with automatic refund policy, post-journey reviews |
| **Admin dashboard** | Custom staff-only console with Chart.js analytics and full CRUD for operators, buses, routes, schedules, seats, bookings, passengers, payments and cancellations |
| **Django admin** | All models registered for low-level administration |
| **Extras** | Newsletter, contact messages, policies, custom 404/500 pages, responsive design, local vendored assets (no CDN dependency) |

---

## 🧱 Tech stack

- **Backend:** Python 3.13, Django 5.2
- **Database:** MySQL / MariaDB (XAMPP) with SQLite fallback
- **Frontend:** HTML5, CSS3, JavaScript, Bootstrap 5.3, Font Awesome 6.5, Chart.js 4.4
- **Images/PDF/QR:** Pillow, qrcode, ReportLab
- **Config:** python-dotenv
- **Fonts:** Outfit + Inter (self-hosted)

All CSS, JS, fonts and images are stored locally under `static/`, so the site works without an internet connection.

---

## 📁 Project structure

```
BusTicketBookingSystem/
├── config/                 # settings, root URLs, WSGI/ASGI
├── accounts/               # Profile, auth views/forms, password reset
├── buses/                  # Operators, buses, routes, schedules, seats, reviews
├── bookings/               # Booking holds, passengers, cancellations, ticket views
├── payments/               # Payment model, simulated/Razorpay gateways, QR + PDF
├── dashboard/              # Staff-only analytics and CRUD console
├── templates/              # All HTML templates (site + dashboard)
├── static/
│   ├── css/                # base, components, pages, responsive, dashboard
│   ├── js/                 # main, seats, dashboard
│   ├── images/             # local photography, logos, avatars, SVGs
│   └── vendor/             # Bootstrap, Font Awesome, Chart.js, fonts
├── media/                  # Uploaded images and generated QR codes
├── tests/                  # End-to-end integration tests
├── manage.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🚀 Quick start (Windows + XAMPP)

### 1. Prerequisites

- Python 3.11+ (tested on 3.13)
- XAMPP with MySQL/MariaDB running
- A terminal in the project root (`D:\BusTicketBookingSystem`)

### 2. Start MySQL

Open **XAMPP Control Panel → Start MySQL**, or from a terminal:

```powershell
C:\xampp\mysql\bin\mysqld.exe --defaults-file=C:\xampp\mysql\bin\my.ini --standalone
```

### 3. Create the database and user

Open phpMyAdmin (`http://localhost/phpmyadmin`) or run:

```sql
CREATE DATABASE busgo_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER 'busgo_user'@'localhost' IDENTIFIED BY 'busgo_pass_2026';
GRANT ALL PRIVILEGES ON busgo_db.* TO 'busgo_user'@'localhost';

-- Needed only if you want to run the automated test suite:
GRANT ALL PRIVILEGES ON test_busgo_db.* TO 'busgo_user'@'localhost';
GRANT CREATE, DROP ON *.* TO 'busgo_user'@'localhost';
FLUSH PRIVILEGES;
```

> Change the password in both MySQL and `.env` if you prefer.

### 4. Create a virtual environment and install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> If PowerShell blocks activation, run
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

### 5. Configure environment

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set at least:

```env
DJANGO_SECRET_KEY=your-long-random-secret
DB_NAME=busgo_db
DB_USER=busgo_user
DB_PASSWORD=busgo_pass_2026
DB_HOST=127.0.0.1
DB_PORT=3306
PAYMENT_MODE=simulated
```

The repository already contains a working `.env` for local XAMPP defaults.

### 6. Run migrations

```powershell
python manage.py makemigrations accounts buses bookings payments
python manage.py migrate
```

### 7. Load realistic demo data

```powershell
python manage.py seed_demo
```

This creates:

- 6 bus operators and 6 buses (seater + sleeper)
- 12 routes and 21 days of schedules (plus past journeys)
- All seat rows for every schedule
- Approved reviews and demo bookings
- Admin and demo user accounts

The command is safe to re-run; it updates existing demo records instead of duplicating them.

### 8. Start the server

```powershell
python manage.py runserver
```

Open **http://127.0.0.1:8000/**

---

## 🔑 Demo credentials

| Role | Email | Password | Where |
| --- | --- | --- | --- |
| **Admin / staff** | `admin@busgo.com` | `Admin@12345` | `/dashboard/` and `/admin/` |
| **Traveller** | `demo@busgo.com` | `Demo@12345` | Main website |

You can also register a fresh traveller account from `/accounts/register/`.

---

## 💳 Payments

### Default: simulated gateway (safe demo)

`PAYMENT_MODE=simulated` (default) shows a clearly-labelled demo gateway with three actions:

- **Pay now** → booking confirmed, ticket + QR + PDF generated
- **Simulate failure** → payment marked failed, no booking confirmed
- **Simulate pending** → payment marked pending, seats remain held until the timer expires

No real money moves and **no card number, CVV or UPI PIN is ever stored**.

### Optional: Razorpay test mode

1. Create Razorpay **test** API keys.
2. In `.env`:

```env
PAYMENT_MODE=razorpay
RAZORPAY_KEY_ID=rzp_test_xxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxx
```

3. Restart the server.

The checkout then creates a Razorpay order and verifies the signature, order ID and amount **server-side** before confirming the booking. If keys are missing or the API call fails, the app gracefully falls back to the simulated gateway.

> Never commit real keys. `.env` is git-ignored.

---

## 🧪 Testing

### Automated integration tests

```powershell
python manage.py test tests -v 2
```

The suite covers **11 end-to-end scenarios**:

- Public page rendering and search
- Registration, email login, logout, profile protection
- Full booking → passenger details → payment → ticket → PDF → verification flow
- Double-booking prevention
- Ticket privacy (other users get 404)
- Payment failure/pending behaviour
- Cancellation and 90% refund calculation
- Staff-only dashboard access
- Dashboard operator CRUD

The tests create and destroy `test_busgo_db` automatically. If your MySQL user cannot create databases, grant the privileges shown in step 3.

### Manual test checklist

1. Search **Bengaluru → Chennai** for tomorrow.
2. Open a bus, select 2 seats, and continue (login required).
3. Fill passenger details and use the simulated gateway → **Pay now**.
4. Open the e-ticket, download the PDF, and scan/verify the QR link.
5. Go to **My bookings**, cancel the booking, and confirm the 90% refund.
6. Log in as admin and open **/dashboard/** — check charts, bookings, payments and seat layout.
7. Try opening another user's ticket URL while signed in as the demo user → should return **404**.
8. Resize to mobile width and verify the nav, seat map and dashboard sidebar work.

### Reset demo data

To start from a clean database:

```powershell
python manage.py flush --no-input
python manage.py migrate
python manage.py seed_demo
```

`flush` keeps migrations but deletes all data and uploaded media references. You may also delete files under `media/qrcodes/` and `media/avatars/` manually.

---

## ⚙️ Configuration reference

| Variable | Default | Purpose |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | dev key | Django secret |
| `DJANGO_DEBUG` | `True` | Debug mode |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,testserver` | Comma-separated hosts |
| `DB_ENGINE` | `mysql` | `mysql` or `sqlite` |
| `DB_NAME` | `busgo_db` | Database name |
| `DB_USER` / `DB_PASSWORD` | `busgo_user` / `busgo_pass_2026` | DB credentials |
| `DB_HOST` / `DB_PORT` | `127.0.0.1` / `3306` | DB address |
| `SEAT_RESERVATION_MINUTES` | `15` | Temporary seat hold duration |
| `MAX_SEATS_PER_BOOKING` | `6` | Per-transaction seat limit |
| `CONVENIENCE_FEE_PER_SEAT` | `30` | Fee in ₹ per seat |
| `GST_PERCENT` | `5` | GST percentage |
| `PAYMENT_MODE` | `simulated` | `simulated` or `razorpay` |
| `SITE_EMAIL` / `SITE_PHONE` / `SITE_ADDRESS` | BUSGO demo details | Shown in header, footer, tickets |
| `EMAIL_BACKEND` | console | Password-reset links print to the terminal |

### SQLite fallback (zero-configuration)

Edit `.env`:

```env
DB_ENGINE=sqlite
```

Then run migrations and seed again:

```powershell
python manage.py migrate
python manage.py seed_demo
```

### Cancellation & refund rules

| Time before departure | Refund |
| --- | --- |
| 24 hours or more | **90%** |
| 6–24 hours | **50%** |
| Under 6 hours | Not permitted |

Refunds are applied automatically, the payment is marked `REFUNDED`, and the seats are released.

---

## 🔐 Security notes

- Passwords are hashed with Django's salted PBKDF2 hasher.
- All booking/payment mutations are CSRF-protected.
- Seat holds and payment confirmation use database transactions and `select_for_update` row locks.
- Payment results are re-validated server-side; the signed payment token prevents tampering.
- Card numbers, CVVs and UPI PINs are **never collected or stored**.
- Tickets are private: only the owner or staff can view/download them.
- The dashboard is restricted with `staff_member_required`.
- `.env`, database files, generated QR codes and uploaded media are git-ignored.

---

## 🛠️ Troubleshooting

**`Access denied for user ...`**
Check `.env` credentials and ensure MySQL is running. If another project's `DB_*` variables are set in your shell, edit `.env` (the project loads it with precedence).

**`mysqlclient` install fails**
On Windows, use a recent Python version with prebuilt wheels, or install the MariaDB connector and XAMPP development files. `pip install mysqlclient` normally works on Python 3.11–3.13.

**Port 3306 already in use**
Stop the other MySQL service or change `DB_PORT` in `.env` and `my.ini`.

**Static files look unstyled**
With `DEBUG=True`, Django serves `static/` automatically. Confirm `static/vendor/bootstrap/bootstrap.min.css` exists. For production, run `collectstatic` behind a web server.

**Password reset email doesn't arrive**
The default `EMAIL_BACKEND` is the console backend — the reset link is printed in the `runserver` terminal. Configure SMTP in `.env` for real email.

**Seats appear locked**
Pending bookings hold seats for 15 minutes. Expired holds are released automatically whenever a booking page or the dashboard loads. You can also run:

```powershell
python manage.py expire_bookings
```

---

## 📌 Known limitations

- The default payment gateway is simulated for demonstration; enable Razorpay test keys for a real gateway flow.
- Email uses the console backend by default.
- No live GPS tracking or SMS notifications.
- Designed for a single-server local deployment; add WhiteNoise/CDN, HTTPS and a production database for public hosting.

---

## 📄 License

This project was built as a complete academic/portfolio demonstration. Demo images are sourced from Unsplash and bundled locally. Use and adapt freely for learning.

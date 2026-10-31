# VoltCare Electricity Billing System

## Project structure
- `electricity_bill_frontend/`: HTML, CSS and JavaScript frontend.
- `electricity_bill_management_backend/`: Flask API, SQL schema, and requirements.

## Important
The tariff in `app.py` is an illustrative academic-project tariff, not a claim about current official KSEB rates. Change the `TARIFF` list only after your project team confirms the tariff rules. This example calculates progressive slabs, not one flat rate for all units.

## 1. Set up MySQL
1. Start MySQL Server.
2. Open MySQL Workbench or the MySQL command line.
3. Run `electricity_bill_management_backend/schema.sql`.
4. The SQL file creates `electricity_bill_db`, its tables, and three dummy consumers with connections, usage records, bills and slab rows.
5. If you already have tables with the old structure, back up your database first. The new `BILL` table has an `Energy_Charge` column and `SLAB_BREAKDOWN` has a `Slab_Amount` column. For a clean demo, use a fresh database.

## 2. Set up the Python backend
Open a terminal in `electricity_bill_management_backend`.

Windows:
```powershell
py -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
$env:DB_HOST="localhost"
$env:DB_USER="root"
$env:DB_PASSWORD="YOUR_MYSQL_PASSWORD"
$env:DB_NAME="electricity_bill_db"
py app.py
```

If your MySQL root account has no password, set `DB_PASSWORD` to an empty string. Keep the terminal running. API address: `http://127.0.0.1:5000`.
Do not put a real database password in frontend JavaScript.

## 3. Run the frontend
Open `electricity_bill_frontend/index.html` with VS Code Live Server, or use another local static web server. The page calls `http://127.0.0.1:5000/api`. Keep the Flask terminal running.

## 4. Test
- The page should show `MySQL connected`.
- Dummy data should appear in the tables.
- Select an unbilled usage record and click **Calculate & generate bill**.
- The backend calculates slab units and charges, creates the bill, and inserts all slab breakdown rows in one database transaction.
- A bill opens in a new tab. Use **Print / Save as PDF** to print it.
- Use **Mark paid** to update payment status in MySQL.

## 5. Example calculation
For 120 units using this demo tariff:
- First 50 × ₹3.25 = ₹162.50
- Next 50 × ₹4.15 = ₹207.50
- Remaining 20 × ₹5.25 = ₹105.00
- Energy charge = ₹162.50 + ₹207.50 + ₹105.00 = **₹475.00**
- If subsidy is ₹20.00, final amount = **₹455.00**.

The backend stores the calculated energy charge, subsidy, final amount, and slab rows. The SQL dummy bills use the same illustrative tariff.

## API routes
- `GET /api/health`
- `GET, POST /api/consumers`
- `GET, POST /api/connections`
- `GET, POST /api/usage`
- `GET, POST /api/bills`
- `GET /api/bills/<bill_id>`
- `PATCH /api/bills/<bill_id>/payment`
- `GET /api/slab-breakdowns`
- `GET /api/dashboard`

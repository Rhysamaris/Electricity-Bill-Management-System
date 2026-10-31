from decimal import Decimal, ROUND_HALF_UP
import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
CORS(app)

# Illustrative academic-project tariff, not an official KSEB tariff.
# Progressive slabs: first 50 units at ₹3.25, next 50 at ₹4.15,
# next 100 at ₹5.25, and all additional units at ₹6.50.
TARIFF = [
    {"limit": Decimal("50"), "rate": Decimal("3.25"), "label": "0–50 units"},
    {"limit": Decimal("50"), "rate": Decimal("4.15"), "label": "51–100 units"},
    {"limit": Decimal("100"), "rate": Decimal("5.25"), "label": "101–200 units"},
    {"limit": None, "rate": Decimal("6.50"), "label": "Above 200 units"},
]
CENT = Decimal("0.01")

def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "anagha@2008root"),
        database=os.getenv("DB_NAME", "electricity_bill_db"),
        port=int(os.getenv("DB_PORT", "3306"))
    )

def json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value

def rows_to_dicts(cursor, rows):
    return [{col[0]: json_value(value) for col, value in zip(cursor.description, row)} for row in rows]

def read_json():
    return request.get_json(silent=True) or {}

def error_response(message, status=400):
    return jsonify({"success": False, "error": message}), status

def query_all(sql, params=()):
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute(sql, params)
        return rows_to_dicts(cur, cur.fetchall())
    finally:
        db.close()

def calculate_slabs(units):
    remaining = Decimal(str(units)).quantize(CENT, rounding=ROUND_HALF_UP)
    result, total = [], Decimal("0.00")
    lower = Decimal("0")
    for slab in TARIFF:
        if remaining <= 0:
            break
        available = remaining if slab["limit"] is None else min(remaining, slab["limit"])
        amount = (available * slab["rate"]).quantize(CENT, rounding=ROUND_HALF_UP)
        upper = "above" if slab["limit"] is None else str(lower + slab["limit"])
        result.append({
            "Slab_Range": slab["label"],
            "Units_In_Slab": available,
            "Rate": slab["rate"],
            "Slab_Amount": amount
        })
        total += amount
        remaining -= available
        if slab["limit"] is not None:
            lower += slab["limit"]
    return result, total.quantize(CENT, rounding=ROUND_HALF_UP)

@app.get("/")
def home():
    return jsonify({"message":"Electricity Bill Management System API is running",
                    "endpoints":["/api/health","/api/consumers","/api/connections",
                                 "/api/usage","/api/bills","/api/slab-breakdowns","/api/dashboard"]})

@app.get("/api/health")
def health():
    try:
        db=get_db(); db.close()
        return jsonify({"success":True,"database":"connected"})
    except Error as exc:
        return jsonify({"success":False,"database":"not connected","error":str(exc)}),500

@app.get("/api/consumers")
def get_consumers():
    return jsonify(query_all("""
        SELECT c.Consumer_ID,c.Name,c.Phone,c.Email,
               GROUP_CONCAT(a.Consumer_Address ORDER BY a.Consumer_Address SEPARATOR ', ') AS Address
        FROM CONSUMER c LEFT JOIN CONSUMER_ADDRESS a ON a.Consumer_ID=c.Consumer_ID
        GROUP BY c.Consumer_ID,c.Name,c.Phone,c.Email ORDER BY c.Consumer_ID DESC
    """))

@app.post("/api/consumers")
def add_consumer():
    d=read_json()
    missing=[k for k in ("Name","Phone","Email","Address") if not str(d.get(k,"")).strip()]
    if missing: return error_response("Required fields: "+", ".join(missing))
    db=get_db()
    try:
        cur=db.cursor()
        cur.execute("INSERT INTO CONSUMER(Name,Phone,Email) VALUES(%s,%s,%s)",
                    (d["Name"].strip(),d["Phone"].strip(),d["Email"].strip()))
        cid=cur.lastrowid
        cur.execute("INSERT INTO CONSUMER_ADDRESS(Consumer_ID,Consumer_Address) VALUES(%s,%s)",
                    (cid,d["Address"].strip()))
        db.commit()
        return jsonify({"success":True,"Consumer_ID":cid}),201
    except Error as exc:
        db.rollback(); return error_response(str(exc),400)
    finally: db.close()

@app.get("/api/connections")
def get_connections():
    return jsonify(query_all("""
        SELECT cd.Connection_ID,cd.Connection_Type,cd.Status,cd.Meter_No,cd.Consumer_ID,c.Name AS Consumer_Name
        FROM CONNECTION_DETAILS cd JOIN CONSUMER c ON c.Consumer_ID=cd.Consumer_ID
        ORDER BY cd.Connection_ID DESC
    """))

@app.post("/api/connections")
def add_connection():
    d=read_json()
    missing=[k for k in ("Connection_Type","Status","Meter_No","Consumer_ID") if d.get(k) in (None,"")]
    if missing:return error_response("Required fields: "+", ".join(missing))
    if d["Status"] not in ("Active","Inactive"):return error_response("Status must be Active or Inactive.")
    try:
        db=get_db();cur=db.cursor()
        cur.execute("""INSERT INTO CONNECTION_DETAILS(Connection_Type,Status,Meter_No,Consumer_ID)
                       VALUES(%s,%s,%s,%s)""",(d["Connection_Type"],d["Status"],d["Meter_No"],d["Consumer_ID"]))
        cid=cur.lastrowid;db.commit();return jsonify({"success":True,"Connection_ID":cid}),201
    except Error as exc:return error_response(str(exc),400)
    finally:
        if 'db' in locals() and db.is_connected():db.close()

@app.get("/api/usage")
def get_usage():
    return jsonify(query_all("""
        SELECT u.Record_ID,u.Read_Date,u.Units_Consumed,u.Connection_ID,cd.Meter_No,c.Name AS Consumer_Name
        FROM USAGE_RECORD u JOIN CONNECTION_DETAILS cd ON cd.Connection_ID=u.Connection_ID
        JOIN CONSUMER c ON c.Consumer_ID=cd.Consumer_ID ORDER BY u.Record_ID DESC
    """))

@app.post("/api/usage")
def add_usage():
    d=read_json()
    missing=[k for k in ("Read_Date","Units_Consumed","Connection_ID") if d.get(k) in (None,"")]
    if missing:return error_response("Required fields: "+", ".join(missing))
    try:
        units=Decimal(str(d["Units_Consumed"]))
        if not units.is_finite() or units<0:return error_response("Units consumed must be a non-negative number.")
        db=get_db();cur=db.cursor()
        cur.execute("""SELECT Status FROM CONNECTION_DETAILS WHERE Connection_ID=%s""",(d["Connection_ID"],))
        row=cur.fetchone()
        if not row:return error_response("Connection not found.",404)
        if row[0]!="Active":return error_response("Cannot record usage for an inactive connection.")
        cur.execute("""INSERT INTO USAGE_RECORD(Read_Date,Units_Consumed,Connection_ID) VALUES(%s,%s,%s)""",
                    (d["Read_Date"],units,d["Connection_ID"]))
        rid=cur.lastrowid;db.commit();return jsonify({"success":True,"Record_ID":rid}),201
    except (ValueError,TypeError):return error_response("Units_Consumed must be a number.")
    except Error as exc:return error_response(str(exc),400)
    finally:
        if 'db' in locals() and db.is_connected():db.close()

@app.get("/api/bills")
def get_bills():
    return jsonify(query_all("""
        SELECT b.Bill_ID,b.Payment_Status,b.Subsidy,b.Energy_Charge,b.Final_Amount,b.Due_Date,b.Bill_Date,
               b.Record_ID,u.Units_Consumed,u.Read_Date,cd.Connection_ID,cd.Meter_No,cd.Consumer_ID,c.Name AS Consumer_Name
        FROM BILL b JOIN USAGE_RECORD u ON u.Record_ID=b.Record_ID
        JOIN CONNECTION_DETAILS cd ON cd.Connection_ID=u.Connection_ID
        JOIN CONSUMER c ON c.Consumer_ID=cd.Consumer_ID ORDER BY b.Bill_ID DESC
    """))

@app.get("/api/bills/<int:bill_id>")
def get_bill(bill_id):
    rows=query_all("""
        SELECT b.Bill_ID,b.Payment_Status,b.Subsidy,b.Energy_Charge,b.Final_Amount,b.Due_Date,b.Bill_Date,
               b.Record_ID,u.Units_Consumed,u.Read_Date,cd.Connection_ID,cd.Meter_No,cd.Consumer_ID,c.Name AS Consumer_Name
        FROM BILL b JOIN USAGE_RECORD u ON u.Record_ID=b.Record_ID
        JOIN CONNECTION_DETAILS cd ON cd.Connection_ID=u.Connection_ID
        JOIN CONSUMER c ON c.Consumer_ID=cd.Consumer_ID WHERE b.Bill_ID=%s
    """,(bill_id,))
    if not rows:return error_response("Bill not found.",404)
    bill=rows[0]
    bill["slab_breakdown"]=query_all("""SELECT Breakdown_ID,Bill_ID,Slab_Range,Units_In_Slab,Rate,Slab_Amount
                                        FROM SLAB_BREAKDOWN WHERE Bill_ID=%s ORDER BY Breakdown_ID""",(bill_id,))
    return jsonify(bill)

@app.post("/api/bills")
def add_bill():
    d=read_json()
    missing=[k for k in ("Record_ID","Bill_Date","Due_Date") if d.get(k) in (None,"")]
    if missing:return error_response("Required fields: "+", ".join(missing))
    try:
        subsidy=Decimal(str(d.get("Subsidy",0))).quantize(CENT,rounding=ROUND_HALF_UP)
        if not subsidy.is_finite() or subsidy<0:return error_response("Subsidy must be a non-negative number.")
        db=get_db()
        try:
            db.start_transaction()
            cur=db.cursor(dictionary=True)
            cur.execute("""SELECT u.Record_ID,u.Units_Consumed FROM USAGE_RECORD u
                           WHERE u.Record_ID=%s FOR UPDATE""",(d["Record_ID"],))
            usage=cur.fetchone()
            if not usage:
                db.rollback();return error_response("Usage record not found.",404)
            cur.execute("SELECT Bill_ID FROM BILL WHERE Record_ID=%s",(d["Record_ID"],))
            if cur.fetchone():
                db.rollback();return error_response("A bill already exists for this usage record.")
            slab_rows,energy=calculate_slabs(usage["Units_Consumed"])
            final=max(Decimal("0.00"),energy-subsidy).quantize(CENT,rounding=ROUND_HALF_UP)
            cur.execute("""INSERT INTO BILL(Payment_Status,Subsidy,Energy_Charge,Final_Amount,Due_Date,Bill_Date,Record_ID)
                           VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                        ("Pending",subsidy,energy,final,d["Due_Date"],d["Bill_Date"],d["Record_ID"]))
            bid=cur.lastrowid
            for slab in slab_rows:
                cur.execute("""INSERT INTO SLAB_BREAKDOWN(Rate,Units_In_Slab,Slab_Range,Slab_Amount,Bill_ID)
                               VALUES(%s,%s,%s,%s,%s)""",
                            (slab["Rate"],slab["Units_In_Slab"],slab["Slab_Range"],slab["Slab_Amount"],bid))
            db.commit()
            return jsonify({"success":True,"Bill_ID":bid,"Energy_Charge":float(energy),
                            "Subsidy":float(subsidy),"Final_Amount":float(final),
                            "slab_breakdown":[{k:float(v) if isinstance(v,Decimal) else v for k,v in s.items()} for s in slab_rows]}),201
        except Exception:
            db.rollback();raise
        finally:
            db.close()
    except (ValueError,TypeError):return error_response("Subsidy must be a number.")
    except Error as exc:return error_response(str(exc),400)

@app.patch("/api/bills/<int:bill_id>/payment")
def update_payment_status(bill_id):
    status=read_json().get("Payment_Status")
    if status not in ("Paid","Pending","Overdue"):return error_response("Payment_Status must be Paid, Pending, or Overdue.")
    db=get_db()
    try:
        cur=db.cursor();cur.execute("UPDATE BILL SET Payment_Status=%s WHERE Bill_ID=%s",(status,bill_id))
        if cur.rowcount==0:
            cur.execute("SELECT Bill_ID FROM BILL WHERE Bill_ID=%s",(bill_id,))
            if not cur.fetchone():return error_response("Bill not found.",404)
        db.commit();return jsonify({"success":True,"message":"Payment status updated."})
    finally:db.close()

@app.get("/api/slab-breakdowns")
def get_slab_breakdowns():
    return jsonify(query_all("""
        SELECT sb.Breakdown_ID,sb.Rate,sb.Units_In_Slab,sb.Slab_Range,sb.Slab_Amount,sb.Bill_ID,
               b.Final_Amount,b.Payment_Status FROM SLAB_BREAKDOWN sb JOIN BILL b ON b.Bill_ID=sb.Bill_ID
        ORDER BY sb.Bill_ID DESC,sb.Breakdown_ID
    """))

@app.get("/api/dashboard")
def dashboard():
    rows=query_all("""SELECT (SELECT COUNT(*) FROM CONSUMER) AS total_consumers,
        (SELECT COUNT(*) FROM CONNECTION_DETAILS WHERE Status='Active') AS active_connections,
        (SELECT COUNT(*) FROM USAGE_RECORD) AS total_usage_records,
        (SELECT COUNT(*) FROM BILL) AS total_bills,
        (SELECT COALESCE(SUM(Final_Amount),0) FROM BILL) AS total_bill_amount,
        (SELECT COUNT(*) FROM BILL WHERE Payment_Status='Paid') AS paid_bills,
        (SELECT COUNT(*) FROM BILL WHERE Payment_Status<>'Paid') AS pending_bills""")
    return jsonify(rows[0] if rows else {})

@app.errorhandler(404)
def not_found(_):return jsonify({"success":False,"error":"API route not found."}),404

@app.errorhandler(500)
def server_error(_):return jsonify({"success":False,"error":"Internal server error."}),500

if __name__=="__main__":
    app.run(host="127.0.0.1",port=5000,debug=True)

from flask import Flask, render_template, request, redirect, session, Response
import sqlite3
import random
from datetime import datetime
import csv
import requests

app = Flask(__name__)
app.secret_key = "secretkey"


# HOME
@app.route("/")
def home():
    return render_template("home.html")


# REGISTER
@app.route("/register", methods=["GET","POST"])
def register():

    if request.method == "POST":

        roll = request.form["roll"]
        password = request.form["password"]
        name = request.form["name"]
        branch = request.form["branch"]
        section = request.form["section"]
        year = request.form["year"]
        hostel = request.form["hostel"]
        bus = request.form["bus"]

        conn = sqlite3.connect("fees.db")
        cur = conn.cursor()

        cur.execute("CREATE TABLE IF NOT EXISTS students(roll TEXT PRIMARY KEY,password TEXT,name TEXT,branch TEXT,section TEXT,year TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS fees(roll TEXT,fee_type TEXT,total_amount INTEGER,paid_amount INTEGER)")
        cur.execute("""
CREATE TABLE IF NOT EXISTS payments(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_no INTEGER,
    roll TEXT,
    fee_type TEXT,
    amount INTEGER,
    date TEXT
)
""")
        cur.execute("INSERT INTO students VALUES(?,?,?,?,?,?)",(roll,password,name,branch,section,year))

        cur.execute("INSERT INTO fees VALUES(?,?,?,?)",(roll,"Tuition",50000,0))
        cur.execute("INSERT INTO fees VALUES(?,?,?,?)",(roll,"Library",2000,0))

        # If hostel student → only hostel (no bus)
        if hostel == "yes":
            cur.execute("INSERT INTO fees VALUES(?,?,?,?)",(roll,"Hostel",30000,0))

# If NOT hostel → bus optional
        else:
            if bus == "yes":
                cur.execute("INSERT INTO fees VALUES(?,?,?,?)",(roll,"Bus",10000,0))

        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("register.html")


# LOGIN
@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        roll = request.form["roll"]
        password = request.form["password"]

        conn = sqlite3.connect("fees.db")
        cur = conn.cursor()

        cur.execute("SELECT * FROM students WHERE roll=? AND password=?",(roll,password))
        user = cur.fetchone()

        conn.close()

        if user:
            session["roll"] = roll
            return redirect("/dashboard")

    return render_template("login.html")


# DASHBOARD
@app.route("/dashboard")
def dashboard():
    if "roll" not in session:
        return redirect("/login")

    roll = session["roll"]

    conn = sqlite3.connect("fees.db")
    cur = conn.cursor()

    cur.execute("SELECT fee_type,total_amount,paid_amount FROM fees WHERE roll=?",(roll,))
    fees = cur.fetchall()

    cur.execute("SELECT SUM(total_amount), SUM(paid_amount) FROM fees WHERE roll=?", (roll,))
    totals = cur.fetchone()

    total_fee = totals[0] if totals[0] else 0
    paid_fee = totals[1] if totals[1] else 0
    due_fee = total_fee - paid_fee

    conn.close()

    return render_template("dashboard.html",
                           fees=fees,
                           total_fee=total_fee,
                           paid_fee=paid_fee,
                           due_fee=due_fee)


# PAY FEE
@app.route("/pay", methods=["POST"])
def pay():
    if "roll" not in session:
        return redirect("/login")

    roll = session["roll"]
    fee_type = request.form["fee_type"]
    amount = int(request.form["amount"])

    conn = sqlite3.connect("fees.db")
    cur = conn.cursor()

    #CHECK REMAINING FEE
    cur.execute("SELECT total_amount, paid_amount FROM fees WHERE roll=? AND fee_type=?", (roll, fee_type))
    fee = cur.fetchone()

    total_amount = fee[0]
    paid_amount = fee[1]

    remaining = total_amount - paid_amount

    if amount > remaining:
        conn.close()
        return "Payment exceeds remaining fee amount!"

    cur.execute("UPDATE fees SET paid_amount = paid_amount + ? WHERE roll=? AND fee_type=?",(amount,roll,fee_type))

    cur.execute("SELECT name,branch,section,year FROM students WHERE roll=?",(roll,))
    student = cur.fetchone()

    name = student[0]
    branch = student[1]
    section = student[2]
    year = student[3]

    receipt_no = random.randint(100000,999999)
    date = datetime.now().strftime("%Y-%m-%d %H:%M")

    cur.execute("INSERT INTO payments (receipt_no, roll, fee_type, amount, date) VALUES (?,?,?,?,?)",
            (receipt_no, roll, fee_type, amount, date))
    conn.commit()

    # SMS MESSAGE
    message = f"""
ABC College of Engineering Fee Payment Successful
Student: {name}
Fee Type: {fee_type}
Amount: {amount}
Receipt No: {receipt_no}
Date & Time: {date}
"""

    url = "https://www.fast2sms.com/dev/bulkV2"

    payload = {
        "message": message,
        "language": "english",
        "route": "q",
        "numbers": "STUDENT_MOBILE_NUMBER"
    }

    headers = {
        "authorization": "YOUR_FAST2SMS_API_KEY"
    }

    requests.post(url, data=payload, headers=headers)

    conn.close()

    return render_template("receipt.html",
                           receipt_no=receipt_no,
                           date=date,
                           name=name,
                           roll=roll,
                           branch=branch,
                           section=section,
                           year=year,
                           fee_type=fee_type,
                           amount=amount)


# STUDENT HISTORY
@app.route("/view_history")
def view_history():
    if "roll" not in session:
        return redirect("/login")
    roll = session["roll"]

    conn = sqlite3.connect("fees.db")
    cur = conn.cursor()

    cur.execute("SELECT receipt_no,fee_type,amount,date FROM payments WHERE roll=? ORDER BY date DESC",(roll,))
    payments = cur.fetchall()

    conn.close()

    return render_template("history.html",payments=payments)

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        # simple admin credentials
        if username == "admin" and password == "admin123":
            session["admin"] = True
            return redirect("/admin")

        else:
            return "Invalid Admin Credentials"

    return render_template("admin_login.html")

# ADMIN DASHBOARD
@app.route("/admin")
def admin():

    if "admin" not in session:
        return redirect("/admin_login")

    conn = sqlite3.connect("fees.db")
    cur = conn.cursor()

    roll = request.args.get("roll")
    fee_type = request.args.get("fee_type")
    date = request.args.get("date")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    query = "SELECT * FROM payments WHERE 1=1"
    params = []

    if roll:
        query += " AND roll=?"
        params.append(roll)

    if fee_type:
        query += " AND fee_type=?"
        params.append(fee_type)

    if date:
        query += " AND date LIKE ?"
        params.append("%"+ date +"%")

    if from_date and to_date:
        query += " AND date BETWEEN ? AND ?"
        params.append(from_date)
        params.append(to_date)

    query += " ORDER BY date DESC"

    cur.execute(query, params)

    data = cur.fetchall()

    conn.close()

    return render_template("admin.html", data=data)

@app.route("/admin_logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/admin_login")

# DAILY COLLECTION
@app.route("/daily")
def daily():

    today = datetime.now().strftime("%d-%m-%Y")

    conn = sqlite3.connect("fees.db")
    cur = conn.cursor()

    cur.execute("SELECT SUM(amount) FROM payments WHERE date LIKE ?",('%'+today+'%',))
    total = cur.fetchone()[0]

    conn.close()

    if total is None:
        total = 0

    return render_template("daily.html", total=total, date=today)


# MONTHLY COLLECTION
@app.route("/monthly")
def monthly():

    month = datetime.now().strftime("%m-%Y")

    conn = sqlite3.connect("fees.db")
    cur = conn.cursor()

    cur.execute("SELECT SUM(amount) FROM payments WHERE date LIKE ?",('%'+month+'%',))
    total = cur.fetchone()[0]

    conn.close()

    if total is None:
        total = 0

    return render_template("monthly.html", total=total, month=month)


# DOWNLOAD PAYMENTS
@app.route("/download")
def download():

    conn = sqlite3.connect("fees.db")
    cur = conn.cursor()

    cur.execute("SELECT * FROM payments")
    data = cur.fetchall()

    conn.close()

    def generate():

        yield "Receipt No,Roll No,Fee Type,Amount,Date\n"

        for row in data:
            yield ",".join(str(i) for i in row) + "\n"

    return Response(generate(),
        mimetype="text/csv",
        headers={"Content-Disposition":"attachment;filename=payments_report.csv"})

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/delete/<int:id>")
def delete(id):

    conn = sqlite3.connect("fees.db")
    cur = conn.cursor()

    # 1. GET PAYMENT DETAILS
    cur.execute("SELECT roll, fee_type, amount FROM payments WHERE id=?", (id,))
    payment = cur.fetchone()

    print("PAYMENT DATA:",payment)

    if payment:
        roll = payment[0]
        fee_type = payment[1]
        amount = payment[2]

        # 2. REDUCE PAID AMOUNT
        cur.execute("""
            UPDATE fees
            SET paid_amount = paid_amount - ?
            WHERE roll=? AND TRIM(LOWER(fee_type)) = TRIM(LOWER(?))
        """, (amount, roll, fee_type))

    cur.execute("DELETE FROM payments WHERE id=?", (id,))

    conn.commit()
    conn.close()

    return redirect("/admin")

@app.route("/graph")
def graph():

    conn = sqlite3.connect("fees.db")
    cur = conn.cursor()

    cur.execute("SELECT date, amount FROM payments")
    data = cur.fetchall()

    conn.close()

    totals = {}

    for row in data:
        d = row[0].split(" ")[0]   # get date only

        if d in totals:
            totals[d] += row[1]
        else:
            totals[d] = row[1]

    dates = sorted(totals.keys())
    amounts = [totals[d] for d in dates]

    return render_template("graph.html", dates=dates, amounts=amounts)

@app.route("/monthly_graph")
def monthly_graph():

    conn = sqlite3.connect("fees.db")
    cur = conn.cursor()

    cur.execute("SELECT date, amount FROM payments")
    data = cur.fetchall()

    conn.close()

    totals = {}

    for row in data:
        # extract month-year
        d = row[0]

        try:
            dt = datetime.strptime(d, "%Y-%m-%d %H:%M")
        except:
        # fallback to old format (dd-mm-yyyy)
            dt = datetime.strptime(d, "%d-%m-%Y %H:%M")

        month = dt.strftime("%m-%Y")

        if month in totals:
            totals[month] += row[1]
        else:
            totals[month] = row[1]

    months = sorted(totals.keys())
    amounts = [totals[m] for m in months]

    return render_template("monthly_graph.html", months=months, amounts=amounts)

@app.route("/pie_chart")
def pie_chart():

    conn = sqlite3.connect("fees.db")
    cur = conn.cursor()

    cur.execute("SELECT fee_type, SUM(amount) FROM payments GROUP BY fee_type")
    data = cur.fetchall()

    conn.close()

    labels = []
    values = []

    for row in data:
        labels.append(row[0])
        values.append(row[1])

    return render_template("pie_chart.html", labels=labels, values=values)

@app.route("/forgot_password", methods=["GET","POST"])
def forgot_password():

    if request.method == "POST":

        roll = request.form["roll"]
        new_password = request.form["password"]

        conn = sqlite3.connect("fees.db")
        cur = conn.cursor()

        cur.execute("UPDATE students SET password=? WHERE roll=?", (new_password, roll))

        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("forgot_password.html")

if __name__ == "__main__":
    app.run(debug=True)
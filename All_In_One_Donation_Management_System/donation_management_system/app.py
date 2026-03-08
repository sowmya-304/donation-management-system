from flask import Flask, render_template, request, redirect, session
from database.db_connection import mysql
import bcrypt
import pandas as pd
from flask import send_file

app = Flask(__name__)
app.secret_key = "donation_secret"

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'donation_system'

mysql.init_app(app)


@app.route("/")
def home():
    return redirect("/login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        phone = request.form["phone"]
        role = request.form["role"]

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        cur = mysql.connection.cursor()

        cur.execute(
            "INSERT INTO users(name,email,password,phone,role) VALUES(%s,%s,%s,%s,%s)",
            (name, email, hashed_password, phone, role)
        )

        mysql.connection.commit()
        cur.close()

        return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        cur = mysql.connection.cursor()

        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()

        if user:
            stored_password = user[3]

            if bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
                session["user_id"] = user[0]
                session["name"] = user[1]
                session["role"] = user[5]

                if user[5] == "admin":
                    return redirect("/admin_dashboard")
                else:
                    return redirect("/dashboard")

        return "Invalid Login"

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():

    if "user_id" in session:
        return render_template("dashboard.html", name=session["name"])

    return redirect("/login")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/profile")
def profile():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT users.name, users.email, users.phone,
           donors.address, donors.city, donors.preferred_donation
    FROM users
    LEFT JOIN donors ON users.user_id = donors.user_id
    WHERE users.user_id=%s
    """, (user_id,))

    donor = cur.fetchone()

    return render_template("donor_profile.html", donor=donor)

@app.route("/edit_profile", methods=["GET","POST"])
def edit_profile():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    if request.method == "POST":

        address = request.form["address"]
        city = request.form["city"]
        preferred = request.form["preferred_donation"]

        cur = mysql.connection.cursor()

        cur.execute(
        "INSERT INTO donors(user_id,address,city,preferred_donation) VALUES(%s,%s,%s,%s)",
        (user_id,address,city,preferred)
        )

        mysql.connection.commit()

        return redirect("/profile")

    return render_template("edit_profile.html")

@app.route("/add_donation", methods=["GET","POST"])
def add_donation():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    cur = mysql.connection.cursor()

    cur.execute("SELECT donor_id FROM donors WHERE user_id=%s",(user_id,))
    donor = cur.fetchone()

    if not donor:
        return "Please complete donor profile first"

    donor_id = donor[0]

    if request.method == "POST":

        dtype = request.form["type"]
        title = request.form["title"]
        description = request.form["description"]
        quantity = request.form["quantity"]
        address = request.form["address"]

        cur.execute("""
        INSERT INTO donations
        (donor_id,donation_type,title,description,quantity,pickup_address)
        VALUES(%s,%s,%s,%s,%s,%s)
        """,(donor_id,dtype,title,description,quantity,address))

        mysql.connection.commit()

        return redirect("/my_donations")

    return render_template("add_donation.html")

@app.route("/my_donations")
def my_donations():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT donation_type,title,quantity,status
    FROM donations
    JOIN donors ON donations.donor_id = donors.donor_id
    WHERE donors.user_id=%s
    """,(user_id,))

    donations = cur.fetchall()

    return render_template("my_donations.html", donations=donations)

@app.route("/admin_dashboard")
def admin_dashboard():

    if "role" not in session or session["role"] != "admin":
        return "Access Denied"

    return render_template("admin_dashboard.html")

@app.route("/manage_donations")
def manage_donations():

    if "role" not in session or session["role"] != "admin":
        return "Access Denied"

    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT donation_id, donation_type, title, quantity, status
    FROM donations
    """)

    donations = cur.fetchall()

    return render_template("manage_donations.html", donations=donations)

@app.route("/approve/<int:id>")
def approve_donation(id):

    cur = mysql.connection.cursor()

    # Update donation status
    cur.execute("UPDATE donations SET status='approved' WHERE donation_id=%s",(id,))

    # Get donation details
    cur.execute("""
    SELECT title, quantity
    FROM donations
    WHERE donation_id=%s
    """,(id,))

    donation = cur.fetchone()

    item_name = donation[0]
    quantity = donation[1]

    # Add to inventory
    cur.execute("""
    INSERT INTO inventory(donation_id,item_name,quantity)
    VALUES(%s,%s,%s)
    """,(id,item_name,quantity))

    mysql.connection.commit()

    return redirect("/manage_donations")

@app.route("/reject/<int:id>")
def reject_donation(id):

    cur = mysql.connection.cursor()

    cur.execute("UPDATE donations SET status='rejected' WHERE donation_id=%s",(id,))

    mysql.connection.commit()

    return redirect("/manage_donations")

@app.route("/add_request", methods=["GET","POST"])
def add_request():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    if request.method == "POST":

        rtype = request.form["type"]
        description = request.form["description"]
        quantity = request.form["quantity"]
        urgency = request.form["urgency"]

        cur = mysql.connection.cursor()

        cur.execute("""
        INSERT INTO requests(user_id,request_type,description,quantity,urgency_level)
        VALUES(%s,%s,%s,%s,%s)
        """,(user_id,rtype,description,quantity,urgency))

        mysql.connection.commit()

        return redirect("/my_requests")

    return render_template("add_request.html")

@app.route("/my_requests")
def my_requests():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT request_type,description,quantity,urgency_level,status
    FROM requests
    WHERE user_id=%s
    """,(user_id,))

    requests = cur.fetchall()

    return render_template("my_requests.html",requests=requests)

@app.route("/manage_requests")
def manage_requests():

    if session.get("role") != "admin":
        return "Access Denied"

    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT request_id,request_type,quantity,urgency_level,status
    FROM requests
    """)

    requests = cur.fetchall()

    return render_template("manage_requests.html",requests=requests)

@app.route("/approve_request/<int:id>")
def approve_request(id):

    cur = mysql.connection.cursor()

    cur.execute("UPDATE requests SET status='approved' WHERE request_id=%s",(id,))

    mysql.connection.commit()

    return redirect("/manage_requests")

@app.route("/reject_request/<int:id>")
def reject_request(id):

    cur = mysql.connection.cursor()

    cur.execute("UPDATE requests SET status='rejected' WHERE request_id=%s",(id,))

    mysql.connection.commit()

    return redirect("/manage_requests")

@app.route("/inventory")
def inventory():

    if session.get("role") != "admin":
        return "Access Denied"

    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT item_id,item_name,quantity,expiry_date
    FROM inventory
    """)

    inventory = cur.fetchall()

    return render_template("inventory.html", inventory=inventory)

@app.route("/add_blood", methods=["GET","POST"])
def add_blood():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    cur = mysql.connection.cursor()

    cur.execute("SELECT donor_id FROM donors WHERE user_id=%s",(user_id,))
    donor = cur.fetchone()

    if not donor:
        return "Please complete donor profile first"

    donor_id = donor[0]

    if request.method == "POST":

        blood_group = request.form["blood_group"]
        last_date = request.form["last_date"]

        cur.execute("""
        INSERT INTO blood_donations(donor_id,blood_group,last_donation_date,eligibility)
        VALUES(%s,%s,%s,1)
        """,(donor_id,blood_group,last_date))

        mysql.connection.commit()

        return redirect("/dashboard")

    return render_template("add_blood_details.html")

@app.route("/blood_donors")
def blood_donors():

    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT users.name,blood_donations.blood_group,
           blood_donations.last_donation_date,
           blood_donations.eligibility
    FROM blood_donations
    JOIN donors ON blood_donations.donor_id = donors.donor_id
    JOIN users ON donors.user_id = users.user_id
    """)

    donors = cur.fetchall()

    return render_template("blood_donors.html", donors=donors)

@app.route("/donate_money", methods=["GET","POST"])
def donate_money():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    cur = mysql.connection.cursor()

    cur.execute("SELECT donor_id FROM donors WHERE user_id=%s",(user_id,))
    donor = cur.fetchone()

    if not donor:
        return "Complete donor profile first"

    donor_id = donor[0]

    if request.method == "POST":

        amount = request.form["amount"]
        method = request.form["method"]
        transaction = request.form["transaction_id"]

        cur.execute("""
        INSERT INTO payments(donor_id,amount,payment_method,transaction_id)
        VALUES(%s,%s,%s,%s)
        """,(donor_id,amount,method,transaction))

        mysql.connection.commit()

        return redirect("/payment_history")

    return render_template("donate_money.html")


@app.route("/payment_history")
def payment_history():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT amount,payment_method,transaction_id,payment_date
    FROM payments
    JOIN donors ON payments.donor_id = donors.donor_id
    WHERE donors.user_id=%s
    """,(user_id,))

    payments = cur.fetchall()

    return render_template("payment_history.html", payments=payments)

@app.route("/reports")
def reports():

    if session.get("role") != "admin":
        return "Access Denied"

    cur = mysql.connection.cursor()

    # Total users
    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]

    # Total donations
    cur.execute("SELECT COUNT(*) FROM donations")
    donations = cur.fetchone()[0]

    # Total requests
    cur.execute("SELECT COUNT(*) FROM requests")
    requests = cur.fetchone()[0]

    # Total payments
    cur.execute("SELECT COUNT(*) FROM payments")
    payments = cur.fetchone()[0]

    return render_template(
        "reports.html",
        users=users,
        donations=donations,
        requests=requests,
        payments=payments
    )


@app.route("/download_report")
def download_report():

    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT donation_type,title,quantity,status
    FROM donations
    """)

    data = cur.fetchall()

    df = pd.DataFrame(data, columns=["Type","Title","Quantity","Status"])

    file_path = "donation_report.csv"
    df.to_csv(file_path, index=False)

    return send_file(file_path, as_attachment=True)

@app.route("/feedback", methods=["GET","POST"])
def feedback():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    if request.method == "POST":

        message = request.form["message"]

        cur = mysql.connection.cursor()

        cur.execute(
        "INSERT INTO feedback(user_id,message) VALUES(%s,%s)",
        (user_id,message)
        )

        mysql.connection.commit()

        return "Feedback Submitted"

    return render_template("feedback.html")

@app.route("/admin_feedback")
def admin_feedback():

    if session.get("role") != "admin":
        return "Access Denied"

    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT users.name,feedback.message,feedback.created_at
    FROM feedback
    JOIN users ON feedback.user_id = users.user_id
    """)

    feedback = cur.fetchall()

    return render_template("admin_feedback.html", feedback=feedback)

if __name__ == "__main__":
    app.run(debug=True)
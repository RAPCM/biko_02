from flask import Flask, render_template, request, session, redirect, url_for, jsonify, flash, render_template
import pandas as pd
import random
import time

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Required for using session

# Load Excel file globally so it doesn't load repeatedly
EXCEL_FILE = "dados.xlsx"
excel_data = pd.read_excel(EXCEL_FILE, sheet_name="Sheet1")

def load_excel(sheet_name):
    return pd.read_excel(EXCEL_FILE, sheet_name=sheet_name)


def save_excel(data, sheet_name):
    with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        data.to_excel(writer, sheet_name=sheet_name, index=False)


@app.route('/register', methods=["GET", "POST"])
def register():
    excel_data_sheet1 = load_excel("Sheet1")
    excel_data_sheet2 = load_excel("Sheet2")

    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        phone = request.form.get("phone")
        bike_name = request.form.get("bike_name")
        bike_id = request.form.get("bike_id")  # User-provided bike ID

        # Check if the bike ID already exists in Sheet1
        existing_bike_ids = set(excel_data_sheet1["bike_id"])
        if int(bike_id) in existing_bike_ids:
            error_message = f"Error: Bike ID {bike_id} already exists"
            return render_template("register.html", error_message=error_message)

        # Generate unique user_id
        existing_user_ids = set(excel_data_sheet2["user_id"])
        user_id = random.randint(1000, 9999)
        while user_id in existing_user_ids:
            user_id = random.randint(1000, 9999)

        # Add data to Sheet1
        new_row_sheet1 = {
            "user": username,
            "user_id": user_id,
            "bike_name": bike_name,
            "bike_id": bike_id,
        }
        excel_data_sheet1 = pd.concat([excel_data_sheet1, pd.DataFrame([new_row_sheet1])], ignore_index=True)
        save_excel(excel_data_sheet1, "Sheet1")

        # Add data to Sheet2
        new_row_sheet2 = {
            "user": username,
            "user_id": user_id,
            "email": email,
            "phone": phone,
        }
        excel_data_sheet2 = pd.concat([excel_data_sheet2, pd.DataFrame([new_row_sheet2])], ignore_index=True)
        save_excel(excel_data_sheet2, "Sheet2")

        # Success message
        flash(f"User {username} created successfully with Bike ID {bike_id}!", "success")
        return redirect(url_for("index"))
    return render_template("register.html")


@app.route('/toggle_bike_status', methods=["POST"])
def toggle_bike_status():
    if "logged_in_user" not in session:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    # Reload the Excel data dynamically
    excel_data_sheet1 = load_excel("Sheet1")
    logged_in_user = session["logged_in_user"]

    # Parse bike_id from JSON request
    request_data = request.get_json()
    bike_id = request_data.get("bike_id")

    if not bike_id:
        return jsonify({"status": "error", "message": "Bike ID is required"}), 400

    # Find the row corresponding to the user's bike
    user_row_index = excel_data_sheet1[(excel_data_sheet1["user"] == logged_in_user) & (excel_data_sheet1["bike_id"] == int(bike_id))].index
    if not user_row_index.empty:
        user_row_index = user_row_index[0]

        # Toggle bike status
        current_status = excel_data_sheet1.at[user_row_index, "bike_status"]
        new_status = 0 if current_status == 1 else 1
        excel_data_sheet1.at[user_row_index, "bike_status"] = new_status

        # Save the updated Excel file
        save_excel(excel_data_sheet1, "Sheet1")

        # Return success message
        return jsonify({"status": "success", "new_status": new_status})
    else:
        return jsonify({"status": "error", "message": "Bike not found"}), 404


@app.route('/api/get_bike_status', methods=["GET"])
def get_bike_status():
    if "logged_in_user" not in session:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    # Dynamically reload the latest Excel data
    excel_data_sheet1 = load_excel("Sheet1")
    logged_in_user = session["logged_in_user"]

    # Find the user's bike
    user_row = excel_data_sheet1[excel_data_sheet1["user"] == logged_in_user]
    if not user_row.empty:
        bike_status = int(user_row.iloc[0]["bike_status"])  # Convert to Python int
        bike_id = int(user_row.iloc[0]["bike_id"])          # Convert to Python int
        return jsonify({"status": "success", "bike_status": bike_status, "bike_id": bike_id})
    else:
        return jsonify({"status": "error", "message": "Bike not found"}), 404




@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Get the username from the form input
        username = request.form.get("username")

        # Check if the username exists in the Excel file
        if username in excel_data["user"].values:
            session["logged_in_user"] = username  # Store username in session
            return render_template("login.html", user=username)  # Load the menu page
        else:
            # Send an error message back to the index page
            message = "User not found"
            return render_template("index.html", message=message)
    
    # Handle GET request
    return render_template("login.html", user="Guest")

@app.route('/notifications')
def notifications():
    if "logged_in_user" not in session:
        return redirect(url_for("index"))  # Redirect to login if not logged in

    # Dynamically reload the latest Excel data
    excel_data_sheet1 = load_excel("Sheet1")

    # Get the logged-in user from session
    logged_in_user = session["logged_in_user"]

    # Filter the Excel data for the logged-in user
    user_data = excel_data_sheet1[excel_data_sheet1["user"] == logged_in_user]

    # Check the bike status and location for notifications
    notifications = []
    for _, row in user_data.iterrows():
        bike_name = row["bike_name"]
        bike_park = row["bike_park"]
        bike_status = row["bike_status"]

        # Notification for bike still parked
        if bike_status == 1:
            notifications.append({
                "message": f"⚠️ {bike_name} is still parked at {bike_park}.",
                "type": "warning",
                "time": time.strftime("%I:%M %p")  # Current time
            })
        # Notification for bike not in the same place
        elif bike_status == 0:
            notifications.append({
                "message": f"❗ {bike_name} is not at {bike_park} anymore!",
                "type": "danger",
                "time": time.strftime("%I:%M %p")  # Current time
            })

    return render_template('notifications.html', notifications=notifications)


@app.route('/stats')
def stats():
    if "logged_in_user" not in session:
        return redirect(url_for("index"))  # Redirect to login if not logged in

    # Get the logged-in user from session
    logged_in_user = session["logged_in_user"]

    # Filter the Excel data for the logged-in user
    user_data = excel_data[excel_data["user"] == logged_in_user].iloc[0]

    # Extract the ride stats
    ride_stats = {
        "total_km": user_data.get("km_ridden", 0),  # Total kilometers
        "total_time": user_data.get("trip_time", 0),  # Total trip time
        "average_speed": user_data.get("avg_speed", 0)  # Optional: Average speed
    }

    # Render the stats.html page with user ride data
    return render_template("stats.html", user=logged_in_user, stats=ride_stats)


@app.route("/analytics")
def analytics():
    if "logged_in_user" not in session:
        return redirect(url_for("index"))  # Redirect to login if not logged in

    # Get the logged-in user from session
    logged_in_user = session["logged_in_user"]

    # Filter Excel data for the logged-in user
    user_data = excel_data[excel_data["user"] == logged_in_user].iloc[0]

    # Extract bike information
    bike_info = {
        "bike_park": user_data["bike_park"],
        "bike_id": user_data["bike_id"],
        "bike_name": user_data["bike_name"],
        "battery": user_data["bike_bat"],
        "coordinates": user_data["bike_coord"]
    }

    print(bike_info)

    # Render analytics.html with the logged-in user's data
    return render_template("analytics.html", user=logged_in_user, bike_info=bike_info)



@app.route("/map")
def map_view():
    # Load data from the Excel file
    bike_data = pd.read_excel(EXCEL_FILE, sheet_name="Sheet1")
    station_data = pd.read_excel(EXCEL_FILE, sheet_name="Sheet3")  # Load station data

    # Extract station coordinates and occupancy
    station_locations = []
    for _, row in station_data.iterrows():
        if pd.notna(row["coord"]) and pd.notna(row["occup"]):
            station_locations.append({
                "coords": row["coord"],
                "popup": row["occup"]
            })

    # Extract bike coordinates and locations for single-bike-per-user
    bike_locations = []
    for _, row in bike_data.iterrows():
        if pd.notna(row["bike_coord"]) and pd.notna(row["bike_park"]):
            bike_locations.append({"coords": row["bike_coord"], "popup": row["bike_name"]})

    # Render map.html with bike and station location data
    return render_template("map.html", station_locations=station_locations, bike_locations=bike_locations)



@app.route('/logout')
def logout():
    session.pop("logged_in_user", None)  # Clear session
    return redirect(url_for("index"))


@app.route('/receive_json', methods=['POST'])
def receive_json():
    try:
        # Get JSON data from the request
        json_data = request.get_json()

        if not json_data:
            return jsonify({"status": "error", "message": "No JSON data received"}), 400

        # Log the received data (for debugging)
        print("Received JSON:", json_data)

        # Process the JSON data (Example: store it in a file or process it further)
        # Here, let's save the JSON data to a local file
        with open("received_data.json", "w") as f:
            import json
            json.dump(json_data, f, indent=4)

        # Return a success response
        return jsonify({"status": "success", "message": "JSON data received and saved"}), 200

    except Exception as e:
        # Handle errors
        print("Error:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

#if __name__ == "__main__":
#    app.run(host="0.0.0.0", port=8080, debug=True)

if __name__ == "__main__":
    app.run(debug=True)

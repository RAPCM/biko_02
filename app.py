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








# Global dictionary to store commands and associated bike IDs
station_commands = {}

import threading

@app.route('/toggle_bike_status', methods=["POST"])
def toggle_bike_status():
    global station_commands  # Ensure we are modifying the global variable
    if "logged_in_user" not in session:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    # Load Excel data
    excel_data_sheet1 = load_excel("Sheet1")
    station_data = load_excel("Sheet3")
    logged_in_user = session["logged_in_user"]

    request_data = request.get_json()
    bike_id = str(request_data.get("bike_id"))  # Convert to string
    station_name = request_data.get("station_name")

    # Find the user's bike
    user_row_index = excel_data_sheet1[
        (excel_data_sheet1["user"] == logged_in_user) & (excel_data_sheet1["bike_id"] == int(bike_id))
    ].index
    if user_row_index.empty:
        return jsonify({"status": "error", "message": "Bike not found"}), 404

    user_row_index = user_row_index[0]
    current_status = excel_data_sheet1.at[user_row_index, "bike_status"]

    if current_status == 1:
        new_status = 0
        current_command = "unlock"
        excel_data_sheet1.at[user_row_index, "bike_park"] = None
        excel_data_sheet1.at[user_row_index, "bike_coord"] = None
    else:
        if not station_name:
            return jsonify({"status": "error", "message": "Station name is required to lock the bike"}), 400

        station_row = station_data[station_data["statio"] == station_name]
        if station_row.empty:
            return jsonify({"status": "error", "message": "Station not found"}), 404

        new_status = 1
        current_command = "lock"
        excel_data_sheet1.at[user_row_index, "bike_park"] = station_name
        excel_data_sheet1.at[user_row_index, "bike_coord"] = station_row.iloc[0]["coord"]

    station_commands["station"] = {"command": current_command, "bike_id": bike_id}

    start_time = time.time()
    initial_confirmation = confirmation_status.get(bike_id)
    while True:
        updated_confirmation = confirmation_status.get(bike_id)
        if updated_confirmation != initial_confirmation:
            if isinstance(updated_confirmation, dict):
                if updated_confirmation.get("success") is True:
                    excel_data_sheet1.at[user_row_index, "bike_status"] = new_status
                    save_excel(excel_data_sheet1, "Sheet1")
                    print("DB UPDATED")
                    confirmation_status[bike_id] = None
                    station_commands = {}
                    return jsonify({"status": "success", "message": f"Bike status updated to {'locked' if new_status == 1 else 'unlocked'}."})
                elif updated_confirmation.get("success") is False:
                    error_message = updated_confirmation.get("error", "Unknown error occurred")
                    print("Mensagem de erro:", error_message)
                    confirmation_status[bike_id] = None
                    station_commands = {}
                    return jsonify({"status": "error", "message": error_message})

        if time.time() - start_time > 10:
            confirmation_status[bike_id] = None
            station_commands = {}
            return jsonify({"status": "error", "message": "No response received from the device."})

        time.sleep(0.5)




@app.route('/get_command/1', methods=['GET'])
def get_command():
    """
    Return the current command and bike ID for a station.
    """
    if "station" not in station_commands:
        print("No command found for the station.")  # Debugging
        return jsonify({"status": "waiting for biko"})

    command_data = station_commands["station"]
    print(f"get_command called: {command_data}")  # Debugging

    return jsonify({
        "command": command_data["command"],
        "bike_id": int(command_data["bike_id"]),
        "status": "success"
    })


confirmation_status = {}

@app.route('/post_command/1', methods=['POST'])
def post_command():
    """
    Handle confirmation of bike status commands.
    """
    try:
        # Get the JSON payload from the request
        data = request.get_json()
        print("Received POST command from RSU:", data)  # Debugging

        # Update confirmation status
        bike_id = str(data.get("bike_id"))  # Store bike_id as a string
        success = data.get("success", False)
        error = data.get("error", None)

        if bike_id:
            # Store success and error details as a dictionary
            confirmation_status[bike_id] = {
                "success": success,
                "error": error
            }

        # Return a simple success response
        return jsonify({"status": "success", "message": "Command received"}), 200

    except Exception as e:
        # Handle any errors and return a failure response
        print("Error handling POST command:", str(e))
        return jsonify({"status": "error", "message": "Invalid request"}), 400






@app.route('/api/get_bike_status', methods=["GET"])
def get_bike_status():
    if "logged_in_user" not in session:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    try:
        # Reload Excel sheets dynamically
        excel_data_sheet1 = load_excel("Sheet1")
        station_data = load_excel("Sheet3")  # Station data for dropdown

        logged_in_user = session["logged_in_user"]

        # Find the user's bike
        user_row = excel_data_sheet1[excel_data_sheet1["user"] == logged_in_user]
        if not user_row.empty:
            bike_status = int(user_row.iloc[0]["bike_status"])  # 0: unlocked, 1: locked
            bike_id = int(user_row.iloc[0]["bike_id"])
            current_station = user_row.iloc[0]["bike_park"]  # Current station if parked

            # If the bike is locked, only return the current station
            if bike_status == 1:
                available_stations = [
                    {"id": current_station, "name": current_station, "occupancy": None}
                ]
            else:
                # If the bike is unlocked, return all stations from Sheet3
                available_stations = [
                    {"id": row.get("station_id", row["statio"]),  # Use station_id if available, otherwise statio
                     "name": row["statio"],
                     "occupancy": row.get("occup", "N/A")}  # Handle missing occupancy
                    for _, row in station_data.iterrows()
                ]

            return jsonify({
                "status": "success",
                "bike_status": bike_status,
                "bike_id": bike_id,
                "current_station": current_station if bike_status == 1 else None,
                "stations": available_stations,
            })

        return jsonify({"status": "error", "message": "Bike not found"}), 404
    except Exception as e:
        print("Error in get_bike_status:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500












@app.route('/')
def index():
    return render_template('index.html')

@app.route('/nfc')
def nfc():
    return render_template('nfc.html')

@app.route('/park')
def park():
    return render_template('park.html')

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


# Shared list to store notifications (in-memory solution)
theft_notifications = []

@app.route('/api/report-theft', methods=['POST'])
def api_report_theft():
    try:
        data = request.get_json()
        rfid = data.get("rfid")
        rsu_id = data.get("rsu_id")
        timestamp = data.get("timestamp")
        if not rfid or not rsu_id or not timestamp:
            return jsonify({"status": "error", "message": "Missing required data"}), 400

        # Log the theft report (you can also save it to a file or database)
        print(f"Theft Report: your BIKO={rfid} was stolen, Timestamp={timestamp}")

        # Add a dangerous notification
        theft_notifications.append({
            "message": f"❗ Theft reported: your biko {rfid} was stolen.",
            "type": "danger",
            "time": time.strftime("%I:%M %p")  # Current time
        })

        return jsonify({"status": "success", "message": "Theft reported successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



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

    notifications = []

    # Check if there are any theft notifications
    if theft_notifications:
        # Add only the theft notifications and skip further processing
        notifications.extend(theft_notifications)
    else:
        # Generate bike notifications only if there are no theft notifications
        for _, row in user_data.iterrows():
            bike_name = row["bike_name"]
            bike_park = row["bike_park"]
            bike_status = row["bike_status"]

            # Notification for bike still parked
            if bike_status == 1:
                notifications.append({
                    "message": f"✅ {bike_name} is parked at {bike_park}.",
                    "type": "success",
                    "time": time.strftime("%I:%M %p")  # Current time
                })
            elif bike_status == 0:
                notifications.append({
                    "message": f"⚠️ {bike_name} is not parked.",
                    "type": "warning",
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

    # Reload the Excel data dynamically
    excel_data_sheet1 = load_excel("Sheet1")  # Dynamically load the latest data

    # Filter Excel data for the logged-in user
    user_data = excel_data_sheet1[excel_data_sheet1["user"] == logged_in_user]
    if user_data.empty:
        flash("No data found for the logged-in user", "error")
        return redirect(url_for("index"))  # Redirect to index if no user data is found

    user_data = user_data.iloc[0]  # Select the first row of user data

    # Extract bike information
    bike_info = {
        "bike_park": user_data["bike_park"],
        "bike_id": user_data["bike_id"],
        "bike_name": user_data["bike_name"],
        "battery": user_data.get("bike_bat", "N/A"),  # Handle missing battery field gracefully
        "coordinates": user_data["bike_coord"]
    }

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

@app.route('/camera')
def live_camera():
    return render_template('camera.html')

@app.route('/api/get_stations', methods=['GET'])
def get_stations():
    """
    API endpoint to return station data with coordinates and occupancy.
    """
    try:
        # Load the station data from the Excel file (Sheet3)
        station_data = load_excel("Sheet3")

        # Process station data to return in JSON format
        stations = []
        for _, row in station_data.iterrows():
            if pd.notna(row["coord"]) and pd.notna(row["occup"]):
                stations.append({
                    "id": row.get("station_id", None),  # Optional: station ID
                    "coords": row["coord"],
                    "occupancy": row["occup"],
                    "name": row.get("statio", "Unnamed Station")  # Optional station name
                })

        return jsonify({"status": "success", "stations": stations})
    except Exception as e:
        print("Error in get_stations:", str(e))  # Debug: Print the error
        return jsonify({"status": "error", "message": str(e)})



@app.route('/api/locked-devices', methods=['GET'])
def api_locked_devices():
    # Load data from "Sheet1"
    excel_data_sheet1 = load_excel(sheet_name="Sheet1")
    # Filter rows where bike_status is 1 (locked)
    locked_bikes = excel_data_sheet1[excel_data_sheet1["bike_status"] == 1]
    # Extract the bike IDs of locked bikes
    locked_bike_ids = locked_bikes["bike_id"].tolist()
    # Return the locked bike IDs as a JSON response
    return jsonify({"locked_bike_ids": locked_bike_ids})





if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)

#if __name__ == "__main__":
#    app.run(debug=True)

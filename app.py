# app.py
import os
import json
from flask import Flask, request, jsonify, render_template
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__, static_folder=".", template_folder=".")

# --- Firebase init ---
FIREBASE_KEY = os.environ.get("FIREBASE_KEY")

if not FIREBASE_KEY:
    # For local dev you can put path to JSON file in FIREBASE_LOCAL_PATH env var
    local_path = os.environ.get("C:\\Users\\charu\\Downloads\\rover-gps-firebase-adminsdk-fbsvc-764c982a6d.json")
    if local_path and os.path.exists(local_path):
        cred = credentials.Certificate(local_path)
    else:
        raise RuntimeError("FIREBASE_KEY env var not set. On Render put your service-account JSON into FIREBASE_KEY.")
else:
    # FIREBASE_KEY is expected to be raw JSON string (service account). Convert to dict.
    cred_dict = json.loads(FIREBASE_KEY)
    cred = credentials.Certificate(cred_dict)

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()
rover_col = db.collection("rover")
rover_logs = db.collection("rover_logs")
gnss_logs = db.collection("gnss_logs")

# Serve the index.html placed at the repo root
@app.route("/")
def home():
    return app.send_static_file("index.html")

# POST update rover (used if you want to post to Render backend instead of writing to Firebase locally)
@app.route("/rover", methods=["POST"])
def create_or_update_rover():
    data = request.get_json()
    if not data or not data.get("id"):
        return jsonify({"success": False, "error": "JSON with 'id' field required"}), 400

    doc_id = data["id"].strip()
    # use SERVER_TIMESTAMP for timestamp fields
    timestamp = firestore.SERVER_TIMESTAMP

    rover_col.document(doc_id).set({**data, "timestamp": timestamp})
    rover_logs.add({**data, "id": doc_id, "timestamp": timestamp})
    return jsonify({"success": True, "message": "Rover updated and logged"}), 201

# GET current rover data
@app.route("/rover/<doc_id>", methods=["GET"])
def get_rover(doc_id):
    doc = rover_col.document(doc_id.strip()).get()
    if doc.exists:
        return jsonify({"success": True, "data": doc.to_dict()}), 200
    return jsonify({"success": False, "error": "Rover data not found"}), 404

# Get recent logs for a rover
@app.route("/rover-logs/<rover_id>", methods=["GET"])
def get_logs_for_rover(rover_id):
    docs = rover_logs.where("id", "==", rover_id).order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
    logs = [{"log_id": doc.id, **doc.to_dict()} for doc in docs]
    return jsonify({"success": True, "data": logs}), 200

# Latest GNSS
@app.route("/gnss/latest", methods=["GET"])
def get_latest_gnss():
    docs = gnss_logs.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(1).stream()
    latest = None
    for doc in docs:
        latest = {"id": doc.id, **doc.to_dict()}
    if latest:
        return jsonify({"success": True, "data": latest}), 200
    return jsonify({"success": False, "error": "No GNSS data found"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

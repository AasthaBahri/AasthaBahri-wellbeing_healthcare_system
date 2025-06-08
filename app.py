import openai
import request
from googleapiclient.discovery import build
from geopy.geocoders import Nominatim
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# === CONFIGURE DATABASE ===
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///emergency_data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# === INITIALIZE DB ===
db = SQLAlchemy(app)

# === OPENAI AND YOUTUBE KEYS ===
openai.api_key = "add_your_own_api"
youtube_api_key = "add_your_api"
youtube = build("youtube", "v3", developerKey=youtube_api_key)

# === DATABASE MODEL ===
class EmergencySubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emergency_type = db.Column(db.String(100))
    location = db.Column(db.String(200))
    age = db.Column(db.String(10))
    health_condition = db.Column(db.String(200))

with app.app_context():
    db.create_all()

# === FUNCTION TO GET YOUTUBE VIDEO ===
def get_video(query):
    try:
        request_youtube = youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            videoDuration="short",
            maxResults=1
        )
        response = request_youtube.execute()
        if 'items' in response and len(response['items']) > 0:
            video_url = "https://www.youtube.com/watch?v=" + response['items'][0]['id']['videoId']
            return video_url
        else:
            return None
    except Exception as e:
        print(f"Error fetching YouTube video: {e}")
        return None

# === FUNCTION TO GET ADVICE FROM CHATGPT ===
def get_emergency_advice(emergency_type, age, health_condition):
    prompt = f"What should a {age}-year-old person with {health_condition} do in case of a {emergency_type} emergency?"
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"Error fetching advice from ChatGPT: {e}")
        return "Sorry, I couldn't fetch personalized advice at the moment."

# === FUNCTION TO FIND NEAREST HOSPITAL ===
def find_nearest_hospital(location_name):
    try:
        geolocator = Nominatim(user_agent="healthcare-system")
        location = geolocator.geocode(location_name)

        if location:
            latitude = location.latitude
            longitude = location.longitude

            # Search for nearby hospitals using lat/lon coordinates
            search_url = f"https://nominatim.openstreetmap.org/search?format=json&limit=5&q=hospital&viewbox={longitude-0.05},{latitude+0.05},{longitude+0.05},{latitude-0.05}&bounded=1"
            headers = {
                "User-Agent": "healthcare-system/1.0 (contact@example.com)"
            }
            response = requests.get(search_url, headers=headers)
            hospitals = response.json()

            if hospitals:
                hospital = hospitals[0]  # Nearest one
                hospital_name = hospital['display_name']
                hospital_lat = hospital['lat']
                hospital_lon = hospital['lon']
                google_maps_url = f"https://www.google.com/maps/search/?api=1&query={hospital_lat},{hospital_lon}"

                return {
                    "name": hospital_name,
                    "lat": hospital_lat,
                    "lon": hospital_lon,
                    "google_maps_url": google_maps_url
                }
            else:
                return {"error": "No hospitals found nearby."}
        else:
            return {"error": "Location not found."}
    except Exception as e:
        print(f"Error in find_nearest_hospital: {e}")
        return {"error": "Something went wrong while fetching hospital data."}


# === GET AMBULANCE NUMBER ===
def get_ambulance_number(city):
    ambulance_numbers = {
        'Delhi': '102',
        'Mumbai': '108',
        'Bangalore': '112',
        'Chennai': '101',
        'Kolkata': '103',
    }
    for key in ambulance_numbers:
        if key.lower() in city.lower():
            return ambulance_numbers[key]
    return "100"

# === RISK LEVEL CHECK ===
def risk_level(e_text):
    keywords_high = ['severe', 'unconscious', 'bleeding', 'chest pain', 'stroke', 'breathing difficulty']
    if any(word in e_text.lower() for word in keywords_high):
        return "High Risk - Please seek emergency help immediately."
    else:
        return "Low/Moderate Risk - Monitor symptoms and consult a doctor if needed."

# === MEDICATION SUGGESTIONS ===
def get_medication_suggestion_from_gpt(emergency_type, health_condition):
    prompt = (
        f"Suggest common over-the-counter medication for a person with "
        f"health condition '{health_condition}' experiencing '{emergency_type}'. "
        "If no specific medication, please advise to consult a doctor."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful medical assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"Error fetching medication suggestion from ChatGPT: {e}")
        return "Please consult a healthcare professional for medication advice."


# === DISEASE ALERT ===
def disease_awareness_alert(e_text):
    alerts = {
        'covid': "COVID-19 Alert: Follow social distancing, wear masks, and sanitize hands regularly.",
        'dengue': "Dengue Alert: Prevent mosquito breeding and seek medical help if you have fever and rash.",
        'malaria': "Malaria Alert: Use mosquito nets and seek immediate treatment if you have fever and chills."
    }
    for disease, alert in alerts.items():
        if disease in e_text.lower():
            return alert
    return None

# === MENTAL HEALTH SUPPORT ===
def get_mental_health_support_link():
    return "https://www.youtube.com/playlist?list=PLs5_Rtf2P2rP94pI3I_4IKm6kr7V3o1Ax"

# === ROUTES ===
@app.route("/", methods=["GET"])
def home():
    last_five = EmergencySubmission.query.order_by(EmergencySubmission.id.desc()).limit(5).all()
    return render_template("index.html", last_five=last_five)

@app.route("/handle_emergency", methods=["POST"])
def handle_emergency():
    emergency_type = request.form.get("emergency_type")
    location = request.form.get("user_location")
    age = request.form.get("age")
    health_condition = request.form.get("health_condition")

    # Save to DB
    new_entry = EmergencySubmission(
        emergency_type=emergency_type,
        location=location,
        age=age,
        health_condition=health_condition
    )
    db.session.add(new_entry)
    db.session.commit()

    # Call functions
    advice = get_emergency_advice(emergency_type, age, health_condition)
    video_url = get_video(emergency_type)
    hospital_info = find_nearest_hospital(location)
    ambulance_number = get_ambulance_number(location)
    risk = risk_level(emergency_type)

    medication_info = get_medication_suggestion_from_gpt(emergency_type, health_condition)

    alert_msg = disease_awareness_alert(emergency_type)
    mental_health_url = get_mental_health_support_link()
    last_five = EmergencySubmission.query.order_by(EmergencySubmission.id.desc()).limit(5).all()

    return render_template("index.html",
                           advice=advice,
                           video_url=video_url,
                           nearest_hospital=hospital_info,
                           ambulance_number=ambulance_number,
                           risk_level=risk,
                           medication_info=medication_info,
                           disease_alert=alert_msg,
                           mental_health_url=mental_health_url,
                           last_five=last_five,
                           emergency_type=emergency_type,
                           location=location,
                           age=age,
                           health_condition=health_condition
                           )

if __name__ == "__main__":
    app.run(debug=True)



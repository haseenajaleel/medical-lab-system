from fastapi import FastAPI, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from database import bookings
from models import Booking
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from dotenv import load_dotenv
import os

# ---------------- TWILIO CONFIG ----------------
load_dotenv()
account_sid = os.getenv("ACCOUNT_SID")
auth_token = os.getenv("AUTH_TOKEN")
twilio_whatsapp_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
twilio_sms_number = os.getenv("TWILIO_SMS_NUMBER")

client = Client(account_sid, auth_token)

# ---------------- FASTAPI APP ----------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ---------------- IN-MEMORY SESSIONS ----------------
sessions = {}

def get_session(phone):
    if phone not in sessions:
        sessions[phone] = {"step": "idle"}
    return sessions[phone]

def clear_session(phone):
    sessions[phone] = {"step": "idle"}

# ---------------- WHATSAPP HANDLER ----------------
def handle_whatsapp_message(from_number, body):
    phone = from_number.replace("whatsapp:+91", "").replace("whatsapp:+", "")
    msg = body.strip().lower()
    session = get_session(phone)
    resp = MessagingResponse()

    # GREET / START
    if msg in ["hi", "hello", "hey", "start", "book"]:
        session["step"] = "ask_name"
        resp.message(
            "Welcome to MedLab Booking!\n\n"
            "I can help you:\n"
            "  *book* - Book a new test\n"
            "  *status* - Check your booking\n"
            "  *cancel* - Cancel a booking\n\n"
            "What is your full name?"
        )
        return str(resp)

    # STATUS
    if msg == "status":
        booking = bookings.find_one({"phone": phone}, {"_id": 0})
        if booking:
            resp.message(
                f"Your booking:\n"
                f"Test: {booking['test']}\n"
                f"Time: {booking['time']}\n"
                f"Status: {booking['status']}"
            )
        else:
            resp.message("No booking found. Send *book* to make one.")
        return str(resp)

    # CANCEL
    if msg == "cancel":
        result = bookings.update_one(
            {"phone": phone, "status": "Booked"},
            {"$set": {"status": "Cancelled"}}
        )
        if result.modified_count:
            resp.message("Your booking has been cancelled. Send *book* to rebook.")
        else:
            resp.message("No active booking found.")
        clear_session(phone)
        return str(resp)

    # MULTI-STEP BOOKING
    step = session.get("step")

    if step == "ask_name":
        session["name"] = body.strip()
        session["step"] = "ask_test"
        resp.message(
            f"Thanks {session['name']}!\n\n"
            "Which tests do you need?\n"
            "1. Blood test\n"
            "2. Urine test\n"
            "3. X-Ray\n"
            "4. ECG\n"
            "5. COVID PCR\n\n"
            "Reply with numbers separated by comma.\n"
            "Example: *1,3* for Blood test and X-Ray"
        )
        return str(resp)
    if step == "ask_test":
        test_map = {
            "1": "Blood test", "2": "Urine test",
            "3": "X-Ray", "4": "ECG", "5": "COVID PCR"
        }
        selected = [t.strip() for t in msg.split(",")]
        session["test"] = [test_map.get(s, s) for s in selected]
        session["step"] = "ask_time"
        resp.message(
            f"Got it - *{', '.join(session['test'])}*\n\n"
            "When would you like your appointment?\n"
            "Format: DD-MM-YYYY HH:MM\n"
            "Example: 10-06-2025 09:30"
        )
        return str(resp)
    if step == "ask_time":
        try:
            datetime.strptime(body.strip(), "%d-%m-%Y %H:%M")
            session["time"] = body.strip()
            session["step"] = "confirm"
            resp.message(
                f"Please confirm:\n\n"
                f"Name: {session['name']}\n"
                f"Test: {session['test']}\n"
                f"Time: {session['time']}\n\n"
                f"Reply *yes* to confirm or *no* to cancel."
            )
        except ValueError:
            resp.message(
                "Wrong format. Use DD-MM-YYYY HH:MM\n"
                "Example: 10-06-2025 09:30"
            )
        return str(resp)

    if step == "confirm":
        if msg == "yes":
            bookings.insert_one({
                "name": session["name"],
                "phone": phone,
                "test": session["test"],
                "time": session["time"],
                "status": "Booked",
                "booked_at": datetime.now().isoformat()
            })
            # Send SMS confirmation
            send_patient_sms(phone, session["name"], session["test"], session["time"])
            clear_session(phone)
            resp.message(
                f"Booking confirmed!\n\n"
                f"Your {session['test']} is scheduled for {session['time']}.\n"
                f"We will remind you before your appointment.\n\n"
                f"Thank you {session['name']}!"
            )
        elif msg == "no":
            clear_session(phone)
            resp.message("Booking cancelled. Send *book* to start again.")
        else:
            resp.message("Please reply *yes* or *no*.")
        return str(resp)

    # FALLBACK
    resp.message(
        "Send *hi* to start booking\n"
        "*status* to check appointment\n"
        "*cancel* to cancel"
    )
    return str(resp)

# ---------------- SMS FUNCTION (FIXED) ----------------
def send_patient_sms(phone, patient_name, test, time):
    try:
        message = client.messages.create(
            body=f"Dear {patient_name}, your {test} is confirmed for {time}. Thank you.",
            from_=twilio_sms_number,  # FIXED - was hardcoded placeholder
            to=f"+91{phone}"
        )
        print("SMS sent:", message.sid)
    except Exception as e:
        print("SMS failed:", str(e))

# ---------------- REMINDER FUNCTION (FIXED) ----------------
def send_reminders():
    print("Running reminder check...")
    all_bookings = list(bookings.find({}, {"_id": 0}))
    current_time = datetime.now().strftime("%d-%m-%Y %H:%M")
    for b in all_bookings:
        if b.get("status") == "Booked" and b.get("time") == current_time:
            send_patient_sms(  # FIXED - was calling send_sms() which doesn't exist
                b["phone"],
                b["name"],
                b["test"],
                b["time"]
            )

# ---------------- SCHEDULER ----------------
scheduler = BackgroundScheduler()
scheduler.add_job(send_reminders, "interval", minutes=1)

@app.on_event("startup")
def start_scheduler():
    if not scheduler.running:
        scheduler.start()

# ---------------- ROUTES ----------------
@app.get("/")
def home():
    return {"message": "Medical Lab Booking API Running"}

@app.get("/bookings")
def get_bookings():
    data = list(bookings.find({}, {"_id": 0}))
    return data

@app.post("/book")
def book_test(data: Booking):
    booking_data = data.dict()
    booking_data["status"] = "Booked"
    result = bookings.insert_one(booking_data)
    send_patient_sms(data.phone, data.name, data.test, data.time)
    return {"message": "Booking Successful", "id": str(result.inserted_id)}

# ---------------- WHATSAPP WEBHOOK ----------------
@app.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...)
):
    twiml = handle_whatsapp_message(From, Body)
    return Response(content=twiml, media_type="application/xml")

# ---------------- REPORT READY ----------------
@app.patch("/booking/{phone}/report-ready")
def report_ready(phone: str):
    bookings.update_one(
        {"phone": phone},
        {"$set": {"status": "Report Ready"}}
    )
    send_patient_sms(
        phone,
        "Patient",
        "your test",
        "is ready. Please collect your report."
    )
    return {"message": f"Report notification sent to {phone}"}
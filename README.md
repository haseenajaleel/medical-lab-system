# Medical Lab Booking System

WhatsApp-based booking and notification system built with FastAPI, MongoDB, and Twilio.

## Features
- Book lab tests via WhatsApp
- Auto reminders before appointment
- Report ready notifications
- Admin panel to view all bookings

## Setup
1. Install dependencies
   pip install -r requirements.txt

2. Start MongoDB
   mongod

3. Start FastAPI
   cd backend
   uvicorn main:app --reload --port 8000

4. Start ngrok
   ngrok http 8000

5. Set Twilio webhook to
   https://your-ngrok-url/whatsapp

## Tech Stack
- FastAPI
- MongoDB
- Twilio WhatsApp API
- APScheduler
- HTML/CSS Admin Panel

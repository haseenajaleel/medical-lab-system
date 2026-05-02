from pymongo import MongoClient

client = MongoClient(
    "mongodb://localhost:27017/",
    serverSelectionTimeoutMS=2000,
    connectTimeoutMS=2000,
    socketTimeoutMS=2000
)

db = client["medical_lab"]
bookings = db["bookings"]
print("MongoDB connected!")
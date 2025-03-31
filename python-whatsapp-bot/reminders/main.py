from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import logging
from typing import List, Optional
from app.utils.whatsapp_utils import get_text_message_input, send_message

app = FastAPI()

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = BackgroundScheduler()
scheduler.start()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simulated database of submitted items
submitted_items = {}

# Pydantic model for request validation
class ReminderRequest(BaseModel):
    reminderName: str
    reminderDate: str
    reminderTime: str
    period: str
    client: str
    message: str
    pendingItems: List[str]

def send_reminder(client: str, message: str, pending_items: List[str] = None):
    # This would be replaced with actual notification logic (WhatsApp, Email, Voice)
    if pending_items:
        logger.info(f"Sending reminder to {client}: {message} | Documents: {', '.join(pending_items)}")
        text = f"reminder : kindly submit remaing documents . you have already submitted " + ", ".join(pending_items) + " ."
        recipient=919943531228
        message_data = get_text_message_input(recipient, text)
        response =send_message(message_data)
        if response == 200:
            print("--------reminder sent successfully")
        else: 
            print("--------reminder failed")
    else:
        logger.info(f"Sending reminder to {client}: {message}")

def schedule_dynamic_reminder(reminder_name: str, client: str, reminder_date: str, reminder_time: str, message: str, pending_items: List[str]):
    now = datetime.now().replace(microsecond=0)
    # Parse the date and time
    date_part = datetime.strptime(reminder_date, "%Y-%m-%d")
    time_part = datetime.strptime(reminder_time, "%H:%M")
    # Combine date and time
    trigger_date = date_part.replace(hour=time_part.hour, minute=time_part.minute, second=0)

    if trigger_date <= now:
        raise HTTPException(status_code=400, detail="Reminder date and time must be in the future")

    # Schedule the reminder
    scheduler.add_job(
        send_reminder,
        'date',
        run_date=trigger_date,
        args=[client, message, pending_items],
        id=f"dynamic_{reminder_name}_{client}_{reminder_date}_{reminder_time.replace(':', '-')}"
    )
    logger.info(f"Scheduled reminder '{reminder_name}' for {client} on {trigger_date}")

@app.post("/create_reminder")
async def create_reminder(reminder: ReminderRequest):
    # For now, we'll schedule a one-time reminder at the specified date and time
    # Later, we can extend this to handle recurring reminders based on the period
    schedule_dynamic_reminder(
        reminder.reminderName,
        reminder.client,
        reminder.reminderDate,
        reminder.reminderTime,
        reminder.message,
        reminder.pendingItems
    )
    return {
        "message": f"Reminder '{reminder.reminderName}' scheduled for {reminder.client} on {reminder.reminderDate} at {reminder.reminderTime}"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
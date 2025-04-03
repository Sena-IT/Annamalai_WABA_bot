
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import logging
import uvicorn
from typing import List, Optional
from app.utils.whatsapp_utils import get_text_message_input, send_message 
from app.utils.database import get_client_reminder_details
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
import psycopg2


app = FastAPI()

# Add CORS middleware to allow cross-origin requests

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_URL = "postgresql://postgres:1234567890@localhost:5432/annamalai_db"

jobstores = {
    'default': SQLAlchemyJobStore(url=DB_URL)  # Using PostgreSQL
}


scheduler = BackgroundScheduler(jobstores=jobstores)
scheduler.start()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


from pydantic import BaseModel
from typing import List, Optional

class PeriodData(BaseModel):
    # Common for all periods, depending on your needs
    fromDate: Optional[str] = None  # For monthly reminders
    toDate: Optional[str] = None    # For monthly reminders
    triggerTime: Optional[str] = None  # For monthly reminders
    
    # For quarterly and halfyearly periods
    months: Optional[List[str]] = None
    reminderDate: Optional[str] = None
    reminderTime: Optional[str] = None

class ReminderData(BaseModel):
    reminderName: str
    reminderDate: str
    reminderTime: str
    client: str
    gstin : str
    message: str
    pendingItems: List[str]
    period: str
    periodData: PeriodData       # Period-specific details as defined above


def send_reminder(client: str, message: str, pending_items: List[str] = None,phone_number=None):
    print("inside send reminder")
    if pending_items:
        recipient = phone_number
        message_data = get_text_message_input(recipient, message)
        response = send_message(message_data)
        if response == 200:
            logger.info("Reminder sent successfully")
        else:
            logger.error("Reminder failed")
    else:
        logger.info(f"Sending reminder to {client}: {message}")


MONTH_MAP = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12
}


def schedule_reminder(reminder):
    job_id_prefix = f"reminder_{reminder.reminderName}_{reminder.client}"

    clinet_reminders = get_client_reminder_details(reminder.gstin)
    for client_id, phone_number, documents, year , month in clinet_reminders:
        pending_tasks = [doc for doc in reminder.pendingItems if doc not in documents ]
        logging.info(f"Pending tasks for {phone_number}: {pending_tasks}")
        
        if reminder.period == "Monthly":
            start_date = datetime.strptime(reminder.periodData.fromDate, "%Y-%m-%d")
            end_date = datetime.strptime(reminder.periodData.toDate, "%Y-%m-%d")
            
            current_date = start_date
            while current_date <= end_date:
                job_id = f"{job_id_prefix}_{current_date.strftime('%Y-%m-%d')}"

                message = f"{reminder.message} : * {', '.join(pending_tasks)}*."

                job_id_created=scheduler.add_job(
                    send_reminder,
                    CronTrigger(day=current_date.day, hour=int(reminder.periodData.triggerTime.split(':')[0]), minute=int(reminder.periodData.triggerTime.split(':')[1])),
                    args=[reminder.client, message, reminder.pendingItems,phone_number],
                    # kwargs={"reminder_name": reminder.reminderName},  # Store reminder name
                    id=job_id,
                    replace_existing=True
                )
                current_date += timedelta(days=1)
                logging.info(f"job created id {job_id_created}")

                logger.info(f"Scheduled {reminder.period} reminder '{reminder.reminderName}' for {reminder.client} on {current_date.strftime('%Y-%m-%d')} at {reminder.periodData.triggerTime}")
            
            print("-------------------------- listing jobs -----------------")
            list_scheduled_jobs()

        elif reminder.period == "Quarterly" or reminder.period == "Halfyearly":
            

            months=reminder.periodData.months

            for month in months:
                print(f"month:{month} , month_map:{MONTH_MAP[month]}")
                job_id = f"{job_id_prefix}_{reminder.reminderDate}_{month}"
                print("job id",job_id)
                      
                job_id_created=scheduler.add_job(
                    send_reminder,
                    CronTrigger(month=MONTH_MAP[month], day=int(reminder.periodData.reminderDate.split('-')[2]),
                                hour=int(reminder.periodData.reminderTime.split(':')[0]), minute=int(reminder.periodData.reminderTime.split(':')[1])),
                    args=[reminder.client, reminder.message, reminder.pendingItems,phone_number],
                    id=job_id,
                    replace_existing=True

                )
                print("job_id_created",job_id_created)
                if job_id_created:


                    logger.info(f"Scheduled {reminder.period} reminder '{reminder.reminderName}' for {reminder.client} on {reminder.periodData.reminderTime} for month {month} {reminder.periodData.reminderDate.split('-')[2]}")
                else:
                    logger.info(f"Failed to schedule {reminder.period} reminder '{reminder.reminderName}'")

            print("-------------------------- listing jobs ---------------------------")
            list_scheduled_jobs()
        else:
            raise HTTPException(status_code=400, detail="Invalid period type")
        

@app.post("/create_reminder")
async def create_reminder(reminder: ReminderData):
    print("reminder json",reminder)
    schedule_reminder(reminder)
    return {"message": f"{reminder.period} reminder '{reminder.reminderName}' scheduled for {reminder.client}"}


# Function to list all scheduled jobs
def list_scheduled_jobs():
    jobs = scheduler.get_jobs()
    for job in jobs:
        print(f"Job ID: {job.id}, Next Run: {job.next_run_time}, Trigger: {job.trigger}")



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)


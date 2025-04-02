# from fastapi import FastAPI, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from apscheduler.schedulers.background import BackgroundScheduler
# from datetime import datetime
# import logging
# from typing import List, Optional
# from app.utils.whatsapp_utils import get_text_message_input, send_message

# app = FastAPI()

# # Add CORS middleware to allow cross-origin requests
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# scheduler = BackgroundScheduler()
# scheduler.start()

# # Configure logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # Simulated database of submitted items
# submitted_items = {}

# # Pydantic model for request validation
# class ReminderRequest(BaseModel):
#     reminderName: str
#     reminderDate: str
#     reminderTime: str
#     period: str
#     client: str
#     message: str
#     pendingItems: List[str]

# def send_reminder(client: str, message: str, pending_items: List[str] = None):
#     # This would be replaced with actual notification logic (WhatsApp, Email, Voice)
#     if pending_items:
#         logger.info(f"Sending reminder to {client}: {message} | Documents: {', '.join(pending_items)}")
#         text = f"reminder : kindly submit remaing documents . you have already submitted " + ", ".join(pending_items) + " ."
#         recipient=919943531228
#         message_data = get_text_message_input(recipient, text)
#         response =send_message(message_data)
#         if response == 200:
#             print("--------reminder sent successfully")
#         else: 
#             print("--------reminder failed")
#     else:
#         logger.info(f"Sending reminder to {client}: {message}")

# def schedule_dynamic_reminder(reminder_name: str, client: str, reminder_date: str, reminder_time: str, message: str, pending_items: List[str], period: Optional[str]=None):
#     now = datetime.now().replace(microsecond=0)
#     # Parse the date and time
#     date_part = datetime.strptime(reminder_date, "%Y-%m-%d")
#     time_part = datetime.strptime(reminder_time, "%H:%M")
#     # Combine date and time
#     trigger_date = date_part.replace(hour=time_part.hour, minute=time_part.minute, second=0)

#     if trigger_date <= now:
#         raise HTTPException(status_code=400, detail="Reminder date and time must be in the future")
    
#     job_id = f"dynamic_{reminder_name}_{client}_{reminder_date}_{reminder_time.replace(':', '-')}"


#     # Schedule the reminder
#     scheduler.add_job(
#         send_reminder,
#         'date',
#         run_date=trigger_date,
#         args=[client, message, pending_items],
#         id=job_id
#     )
#     logger.info(f"Scheduled reminder '{reminder_name}' for {client} on {trigger_date}")


# @app.post("/create_reminder")
# async def create_reminder(reminder: ReminderRequest):
#     # For now, we'll schedule a one-time reminder at the specified date and time
#     # Later, we can extend this to handle recurring reminders based on the period
#     schedule_dynamic_reminder(
#         reminder.reminderName,
#         reminder.client,
#         reminder.reminderDate,
#         reminder.reminderTime,
#         reminder.message,
#         reminder.pendingItems,
#         reminder.period
#     )
#     return {
#         "message": f"Reminder '{reminder.reminderName}' scheduled for {reminder.client} on {reminder.reminderDate} at {reminder.reminderTime}"
#     }

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import logging
from typing import List, Optional
from app.utils.whatsapp_utils import get_text_message_input, send_message 
from app.utils.database import get_client_reminders_gstin

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

    clinet_reminders = get_client_reminders_gstin(reminder.gstin)
    for client_id, phone_number, sub_reminders, parent_reminder in clinet_reminders:
        reminders_dict = sub_reminders[0]
        pending_tasks = [task for task, status in reminders_dict.items() if not status]
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
                    id=job_id,
                    replace_existing=True
                )
                current_date += timedelta(days=1)
                logging.info(f"job created id {job_id_created}")

                logger.info(f"Scheduled {reminder.period} reminder '{reminder.reminderName}' for {reminder.client} on {current_date.strftime('%Y-%m-%d')} at {reminder.periodData.triggerTime}")



        elif reminder.period == "Quarterly" or reminder.period == "Halfyearly":
            
            # job_id = f"{job_id_prefix}_{reminder.reminderDate}"

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


        else:
            raise HTTPException(status_code=400, detail="Invalid period type")
        

@app.post("/create_reminder")
async def create_reminder(reminder: ReminderData):
    print("reminder json",reminder)
    schedule_reminder(reminder)
    return {"message": f"{reminder.period} reminder '{reminder.reminderName}' scheduled for {reminder.client}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

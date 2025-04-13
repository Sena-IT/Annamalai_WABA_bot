from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import logging
import uvicorn
from typing import List, Optional
from app.utils.whatsapp_utils import get_text_message_input, send_message , get_reminder_template_input
from app.utils.database import get_client_reminder_details , upload_document, getAllDataFromSQL, updateLateFeeDataToSQL
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
import psycopg2
import ast

# Month mapping dictionary
MONTH_MAP = {
    'January': 1,
    'February': 2,
    'March': 3,
    'April': 4,
    'May': 5,
    'June': 6,
    'July': 7,
    'August': 8,
    'September': 9,
    'October': 10,
    'November': 11,
    'December': 12
}

app = FastAPI()

# Add CORS middleware to allow cross-origin requests

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
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
    fromDay: Optional[str] = None
    toDay: Optional[str] = None
    triggerTime: Optional[str] = None
    months: Optional[List[str]] = None
    reminderFromDate: Optional[str] = None
    reminderToDate: Optional[str] = None
    reminderTime: Optional[str] = None

class ReminderData(BaseModel):
    reminderName: str
    reminderFromDate: str
    reminderToDate: str
    reminderTime: str
    client: Optional[str] = None  # Made optional
    gstin: Optional[str] = None   # Made optional
    message: str
    pendingItems: List[str]
    period: str
    periodData: PeriodData

# class PeriodData(BaseModel):
#      # Common for all periods, depending on your needs
#     fromDay: Optional[str] = None  # Day (1-31)
#     toDay: Optional[str] = None    # Day (1-31)
#     triggerTime: Optional[str] = None  # For monthly reminders
    
#     # For quarterly and halfyearly periods
#     months: Optional[List[str]] = None
#     reminderFromDate: Optional[str] = None
#     reminderToDate: Optional[str] = None
#     reminderTime: Optional[str] = None

# class ReminderData(BaseModel):
#     reminderName: str
#     reminderFromDate: str
#     reminderToDate :str
#     reminderTime: str
#     client: str
#     gstin : str
#     message: str
#     pendingItems: List[str]
#     period: str
#     periodData: PeriodData        # Period-specific details as defined above

class DocumentData(BaseModel):
    client_name: str
    gstin: str
    month: str
    year: str
    documents: List[str]



def send_reminder(gst_number=None, documents_needed: List[str] = None):
    print("inside send reminder")

    dataResponse = getAllDataFromSQL(gst_number)
    
    if isinstance(documents_needed, list) and len(documents_needed) == 1 and isinstance(documents_needed[0], str):
            try:
                documents_needed = ast.literal_eval(documents_needed[0])
            except Exception as e:
                logger.error(f"Failed to parse documents needed: {documents_needed}, error: {e}")
                return

    logger.info(f"Parsed months: {documents_needed}")


    pending_tasks = [doc for doc in documents_needed if doc not in dataResponse[0][3]]   

    llm_response = llm_message(dataResponse[0][0],dataResponse[0][1],dataResponse[0][2],dataResponse[0][3],dataResponse[0][4],dataResponse[0][5],dataResponse[0][6],dataResponse[0][7], documents_needed)



    # late_fee_date = "2025-04-12"

    today = datetime.now()
    late_fee_date = datetime(today.year, today.month, 12)

    # Only calculate late fee if current date is after the 12th
    if today > late_fee_date:
        # Calculate the difference in days
        day_diff = (today - late_fee_date).days  # returns int
        lateFee = dataResponse[0][7] + (dataResponse[0][6] * day_diff)
        updateLateFeeDataToSQL(gst_number, lateFee)
    else:
        print("No late fee. Current date is before or on the 12th.")

    print("pending_tasks",pending_tasks)


    if pending_tasks:
        recipient = 919943531228
        message_data = get_text_message_input(recipient, llm_response)
        # message_data = get_reminder_template_input(recipient, llm_response)
        response = send_message(message_data)
        
        if response == 200:
            logger.info("Reminder sent successfully")
        else:
            logger.error("Reminder failed")
    




from dotenv import load_dotenv, set_key, find_dotenv
import os
from openai import OpenAI

dotenv_path = find_dotenv()

load_dotenv(dotenv_path)
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))


def llm_message(name, trade_name, phone_number, documents_submitted, year, month,fee, lateFee, documents_needed):
    prompt = f"""You are a reminder assistant.
    Based on the incoming reminder message given by the user and pending task list.
    Make your response short and crisp for whatsapp message.

    Total Document needed:  {documents_needed}  

    you must calculate the late fee according to the below details and return in the result:
    Fee per day : {fee} Rs. - you must calculate with the current date > 12th of a month \n current Date: {datetime.now()}

    Existing Late fee: {lateFee}, add previous late fee to current late fee and return the result

    Do not show any message related to late fee before 12th of a month.
    
    Pending tasks: Refer "Total Document needed" and {documents_submitted}, if there is any mismatch, please send a reminder to the client.
    
    Reminder message inputs: 

    Name: {name}
    Trade Name: {trade_name} - their company name
    Phone Number: {phone_number} - their phone number
    Documents Submitted: {documents_submitted} - submitted document 
    Year: {year}
    Month: {month}
    
    Generate a structured reminder message to be sent to the client.
    Example reminder message :
    Dear Promoter of M/s (1) and his company name , Please submit the Sales , Purchase Invoices and Bank Statements for the Month of current month's previous month (2) before 12th of (2) current month

    
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[ 
            {"role": "system", "content": "You are a helpful chatbot."},    
            {"role": "user", "content": prompt}
        ],
    )
    
    bot_response = response.choices[0].message.content
    return bot_response


def schedule_reminder(reminder):
    job_id_prefix = f"reminder_{reminder.reminderName}_{reminder.client}"
    
    if reminder.period == "Monthly":
        start_day = int(reminder.periodData.fromDay)
        end_day = int(reminder.periodData.toDay)
        
        for day in range(start_day, end_day + 1):
            job_id = f"{job_id_prefix}_{day}"
            scheduler.add_job(
                send_reminder,
                CronTrigger(day=day, hour=int(reminder.periodData.triggerTime.split(':')[0]), minute=int(reminder.periodData.triggerTime.split(':')[1])),
                args=[reminder.gstin, reminder.pendingItems],
                id=job_id,
                replace_existing=True
            )
            logger.info(f"Scheduled {reminder.period} reminder '{reminder.reminderName}' for {reminder.client} on {day} at {reminder.periodData.triggerTime}")
        
        list_scheduled_jobs()

    elif reminder.period == "Quarterly":
        months = reminder.periodData.months

        if isinstance(months, list) and len(months) == 1 and isinstance(months[0], str):
            try:
                months = ast.literal_eval(months[0])
            except Exception as e:
                logger.error(f"Failed to parse months: {months}, error: {e}")
                return

        logger.info(f"Parsed months: {months}")
        
        for month in months:
            print("month",month)

            start_day = int(reminder.periodData.reminderFromDate)
            end_day = int(reminder.periodData.reminderToDate)
            
            for day in range(start_day, end_day + 1):
                job_id = f"{reminder.period}_reminder_{reminder.reminderName}__{month}_{day}"
                scheduler.add_job(
                    send_reminder,
                    CronTrigger(month=MONTH_MAP[month], day=day,
                                hour=int(reminder.periodData.reminderTime.split(':')[0]), minute=int(reminder.periodData.reminderTime.split(':')[1])),
                    args=[reminder.gstin, reminder.pendingItems],
                    id=job_id,
                    replace_existing=True
                )
                logger.info(f"Scheduled {reminder.period} reminder '{reminder.reminderName}' for {reminder.client} on {day} for month {month}")

        list_scheduled_jobs()

    elif reminder.period == "Yearly":
        months = reminder.periodData.yearlyMonths
        start_day = int(reminder.periodData.yearlyFromDate)
        end_day = int(reminder.periodData.yearlyToDate)
        weekly_frequency = reminder.periodData.weeklyFrequency
        hour = int(reminder.periodData.yearlyTime.split(':')[0])
        minute = int(reminder.periodData.yearlyTime.split(':')[1])

        for month in months:
            month_num = MONTH_MAP[month]
            
            if weekly_frequency == "daily":
                # Schedule daily reminders for each day in the range
                for day in range(start_day, end_day + 1):
                    job_id = f"yearly_daily_{reminder.reminderName}_{month}_{day}"
                    scheduler.add_job(
                        send_reminder,
                        CronTrigger(month=month_num, day=day, hour=hour, minute=minute),
                        args=[reminder.gstin, reminder.pendingItems],
                        id=job_id,
                        replace_existing=True
                    )
                    logger.info(f"Scheduled daily yearly reminder for {reminder.reminderName} on {month} {day}")

            elif weekly_frequency == "every3days":
                # Schedule reminders every 3 days within the range
                for day in range(start_day, end_day + 1, 3):
                    job_id = f"yearly_3days_{reminder.reminderName}_{month}_{day}"
                    scheduler.add_job(
                        send_reminder,
                        CronTrigger(month=month_num, day=day, hour=hour, minute=minute),
                        args=[reminder.gstin, reminder.pendingItems],
                        id=job_id,
                        replace_existing=True
                    )
                    logger.info(f"Scheduled 3-day yearly reminder for {reminder.reminderName} on {month} {day}")

            elif weekly_frequency == "twiceAWeek":
                # Schedule reminders twice a week (e.g., Monday and Thursday)
                for day in range(start_day, end_day + 1):
                    if day % 7 in [0, 3]:  # Monday and Thursday
                        job_id = f"yearly_twice_{reminder.reminderName}_{month}_{day}"
                        scheduler.add_job(
                            send_reminder,
                            CronTrigger(month=month_num, day=day, hour=hour, minute=minute),
                            args=[reminder.gstin, reminder.pendingItems],
                            id=job_id,
                            replace_existing=True
                        )
                        logger.info(f"Scheduled twice-weekly yearly reminder for {reminder.reminderName} on {month} {day}")

            elif weekly_frequency == "onceAWeek":
                # Schedule reminder once a week (e.g., Monday)
                for day in range(start_day, end_day + 1):
                    if day % 7 == 0:  # Monday
                        job_id = f"yearly_once_{reminder.reminderName}_{month}_{day}"
                        scheduler.add_job(
                            send_reminder,
                            CronTrigger(month=month_num, day=day, hour=hour, minute=minute),
                            args=[reminder.gstin, reminder.pendingItems],
                            id=job_id,
                            replace_existing=True
                        )
                        logger.info(f"Scheduled weekly yearly reminder for {reminder.reminderName} on {month} {day}")

        list_scheduled_jobs()

    else:
        raise HTTPException(status_code=400, detail="Invalid period type")


# Function to list all scheduled jobs

def list_scheduled_jobs():
    jobs = scheduler.get_jobs()
    for job in jobs:
        print(f"Job ID: {job.id}, Next Run: {job.next_run_time}, Trigger: {job.trigger}")


class DocumentData(BaseModel):
    client_name: str
    gstin: str
    month: str
    year: str
    documents: List[str]



@app.post("/create_reminder")
async def create_reminder(reminder: ReminderData):
    print("reminder json",reminder)

    # documents_needed = reminder.pendingItems

    # print("document_needed",documents_needed)

    # if isinstance(documents_needed, list) and len(documents_needed) == 1 and isinstance(documents_needed[0], str):
    #         try:
    #             documents_needed = ast.literal_eval(documents_needed[0])
    #         except Exception as e:
    #             logger.error(f"Failed to parse documents needed: {documents_needed}, error: {e}")
    #             return
            
    # for i in documents_needed:

    #     print(f"Parsed months: {i}")
    schedule_reminder(reminder)
    return {"message": f"{reminder.period} reminder '{reminder.reminderName}' scheduled for {reminder.client}"}




@app.post("/submit_gstr1")
async def submit_gstr1(documents: DocumentData):
    print("--------------documents json------\n",documents)

    response = upload_document(documents)
    
    if response["status"] == 200:
        return {"message": response["message"]}
    else:
        raise HTTPException(status_code=response["status"], detail=response["message"])    
   

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)






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
from app.utils.database import get_client_reminder_details , upload_document, getAllDataFromSQL, updateLateFeeDataToSQL
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
     # Common for all periods, depending on your needs
    fromDay: Optional[str] = None  # Day (1-31)
    toDay: Optional[str] = None    # Day (1-31)
    triggerTime: Optional[str] = None  # For monthly reminders
    
    # For quarterly and halfyearly periods
    months: Optional[List[str]] = None
    reminderFromDate: Optional[str] = None
    reminderToDate: Optional[str] = None
    reminderTime: Optional[str] = None

class ReminderData(BaseModel):
    reminderName: str
    reminderFromDate: str
    reminderToDate :str
    reminderTime: str
    client: str
    gstin : str
    message: str
    pendingItems: List[str]
    period: str
    periodData: PeriodData        # Period-specific details as defined above

class DocumentData(BaseModel):
    client_name: str
    gstin: str
    month: str
    year: str
    documents: List[str]



def send_reminder(client: str, message: str, pending_items: List[str] = None,phone_number=None,gst_number=None):
    print("inside send reminder")

    dataResponse = getAllDataFromSQL(gst_number)        

    llm_response = llm_message(dataResponse[0][0],dataResponse[0][1],dataResponse[0][2],dataResponse[0][3],dataResponse[0][4],dataResponse[0][5],dataResponse[0][6],dataResponse[0][7])

    late_fee_date = "2025-04-12"

    # Current date
    current_date = datetime.now()

    # Convert given date to datetime object
    given_date_obj = datetime.strptime(late_fee_date, "%Y-%m-%d")

    # Calculate the difference
    day_diff = given_date_obj - current_date

    lateFee = dataResponse[0][7]  + (dataResponse[0][6] * day_diff)

    updateLateFeeDataToSQL(gst_number,lateFee)

    if pending_items:
        recipient = 919943531228
        message_data = get_text_message_input(recipient, llm_response)
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

from dotenv import load_dotenv, set_key, find_dotenv
import os
from openai import OpenAI

dotenv_path = find_dotenv()

load_dotenv(dotenv_path)
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))


def llm_message(name, trade_name, phone_number, documents_submitted, year, month,fee, lateFee):
    prompt = f"""You are a reminder assistant.
    Based on the incoming reminder message given by the user and pending task list.
    Make your response short and crisp for whatsapp message.

    Total Document needed: ["sales_invoice", "purchase_invoice","bank_statement"]    

    you must calculate the late fee according to the below details and return in the result:
    Fee per day : {fee} Rs. - you must calculate with the current date > 12th of a month \n current Date: {datetime.now()}

    Existing Late fee: {lateFee}, add previous late fee to current late fee and return the result

    Do not show any message related to late fee before 12th of a month.
    
    Pending tasks: Refer "Total Document needed" and {documents_submitted}, if there is any mismatch, please send a reminder to the client.
    
    Reminder message: 

    Name: {name}
    Trade Name: {trade_name} - their company name
    Phone Number: {phone_number} - their phone number
    Documents Submitted: {documents_submitted} - submitted document 
    Year: {year}
    Month: {month}
    
    Generate a structured reminder message to be sent to the client."""
    
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

    clinet_reminders = getAllDataFromSQL(reminder.gstin)
    for name, tradeName, phoneNumber, doc , year, month , fee, late_fee in clinet_reminders:
        pending_tasks = [doc for doc in reminder.pendingItems if doc not in doc]
        logging.info(f"Pending tasks for {phoneNumber}: {pending_tasks}")
        
        if reminder.period == "Monthly":
            # start_date = datetime.strptime(reminder.periodData.fromDate, "%Y-%m-%d")
            # end_date = datetime.strptime(reminder.periodData.toDate, "%Y-%m-%d")
            start_day = int(reminder.periodData.fromDay)
            end_day = int(reminder.periodData.toDay)

            print(start_day,type(start_day))
            print(end_day,type(end_day))
 
            
            current_day = start_day
            print(current_day,type(current_day))
            # while current_date <= end_day:
            
            for day in range(start_day, end_day + 1):

                job_id = f"{job_id_prefix}_{current_day}"

                message = f"{reminder.message} : * {', '.join(pending_tasks)}*."

                job_id_created=scheduler.add_job(
                    send_reminder,
                    CronTrigger(day=current_day, hour=int(reminder.periodData.triggerTime.split(':')[0]), minute=int(reminder.periodData.triggerTime.split(':')[1])),
                    args=[reminder.client, message, reminder.pendingItems,phoneNumber,reminder.gstin],
                    # kwargs={"reminder_name": reminder.reminderName},  # Store reminder name
                    id=job_id,
                    replace_existing=True
                )
                logging.info(f"job created id {job_id_created}")

                logger.info(f"Scheduled {reminder.period} reminder '{reminder.reminderName}' for {reminder.client} on {current_day} at {reminder.periodData.triggerTime}")
            
            print("-------------------------- listing jobs -----------------")
            list_scheduled_jobs()

        elif reminder.period == "Quarterly" or reminder.period == "Halfyearly":
            

            months=reminder.periodData.months

            for month in months:
                
                print(f"month:{month} , month_map:{MONTH_MAP[month]}")
                start_day = int(reminder.periodData.reminderFromDate)
                end_day = int(reminder.periodData.reminderToDate)
                current_day = start_day
                
                for day in range(start_day, end_day + 1):

                    
                    job_id = f"{reminder.period} {job_id_prefix}_{month}_{day}"
                    print("job id",job_id)
                        
                    job_id_created=scheduler.add_job(
                        send_reminder,
                        CronTrigger(month=MONTH_MAP[month], day=day,
                                    hour=int(reminder.periodData.reminderTime.split(':')[0]), minute=int(reminder.periodData.reminderTime.split(':')[1])),
                        args=[reminder.client, reminder.message, reminder.pendingItems,phoneNumber],
                        id=job_id,
                        replace_existing=True

                    )
                    print("job_id_created",job_id_created)
                    if job_id_created:
                        logger.info(f"Scheduled {reminder.period} reminder '{reminder.reminderName}' for {reminder.client} on {day} for month {month}")
                    else:
                        logger.info(f"Failed to schedule {reminder.period} reminder '{reminder.reminderName}'")

            print("-------------------------- listing jobs ---------------------------")
            list_scheduled_jobs()
        else:
            raise HTTPException(status_code=400, detail="Invalid period type")
        
#----------------------------------------------------------------------------------------------------------------------------------

    # for client_id, phone_number, documents, year , month in clinet_reminders:
    #     pending_tasks = [doc for doc in reminder.pendingItems if doc not in documents ]
    #     logging.info(f"Pending tasks for {phone_number}: {pending_tasks}")
        
    #     if reminder.period == "Monthly":
    #         # start_date = datetime.strptime(reminder.periodData.fromDate, "%Y-%m-%d")
    #         # end_date = datetime.strptime(reminder.periodData.toDate, "%Y-%m-%d")
    #         start_day = int(reminder.periodData.fromDay)
    #         end_day = int(reminder.periodData.toDay)

    #         print(start_day,type(start_day))
    #         print(end_day,type(end_day))
 
            
    #         current_day = start_day
    #         print(current_day,type(current_day))
    #         # while current_date <= end_day:
            
    #         for day in range(start_day, end_day + 1):

    #             job_id = f"{job_id_prefix}_{current_day}"

    #             message = f"{reminder.message} : * {', '.join(pending_tasks)}*."

    #             job_id_created=scheduler.add_job(
    #                 send_reminder,
    #                 CronTrigger(day=current_day, hour=int(reminder.periodData.triggerTime.split(':')[0]), minute=int(reminder.periodData.triggerTime.split(':')[1])),
    #                 args=[reminder.client, message, reminder.pendingItems,phone_number],
    #                 # kwargs={"reminder_name": reminder.reminderName},  # Store reminder name
    #                 id=job_id,
    #                 replace_existing=True
    #             )
    #             logging.info(f"job created id {job_id_created}")

    #             logger.info(f"Scheduled {reminder.period} reminder '{reminder.reminderName}' for {reminder.client} on {current_day} at {reminder.periodData.triggerTime}")
            
    #         print("-------------------------- listing jobs -----------------")
    #         list_scheduled_jobs()

    #     elif reminder.period == "Quarterly" or reminder.period == "Halfyearly":
            

    #         months=reminder.periodData.months

    #         for month in months:
                
    #             print(f"month:{month} , month_map:{MONTH_MAP[month]}")
    #             start_day = int(reminder.periodData.reminderFromDate)
    #             end_day = int(reminder.periodData.reminderToDate)
    #             current_day = start_day
                
    #             for day in range(start_day, end_day + 1):

                    
    #                 job_id = f"{reminder.period} {job_id_prefix}_{month}_{day}"
    #                 print("job id",job_id)
                        
    #                 job_id_created=scheduler.add_job(
    #                     send_reminder,
    #                     CronTrigger(month=MONTH_MAP[month], day=day,
    #                                 hour=int(reminder.periodData.reminderTime.split(':')[0]), minute=int(reminder.periodData.reminderTime.split(':')[1])),
    #                     args=[reminder.client, reminder.message, reminder.pendingItems,phone_number],
    #                     id=job_id,
    #                     replace_existing=True

    #                 )
    #                 print("job_id_created",job_id_created)
    #                 if job_id_created:
    #                     logger.info(f"Scheduled {reminder.period} reminder '{reminder.reminderName}' for {reminder.client} on {day} for month {month}")
    #                 else:
    #                     logger.info(f"Failed to schedule {reminder.period} reminder '{reminder.reminderName}'")

    #         print("-------------------------- listing jobs ---------------------------")
    #         list_scheduled_jobs()
    #     else:
    #         raise HTTPException(status_code=400, detail="Invalid period type")


#----------------------------------------------------------------------------------------------------------------------------------

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




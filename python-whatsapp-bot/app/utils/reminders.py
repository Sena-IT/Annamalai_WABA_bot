
# Initialize scheduler after defining the cleanup function 

from .whatsapp_utils import get_text_message_input , send_message , sessions 
import logging
from datetime import datetime
import os
import json

from .database import get_clients_reminders

from apscheduler.schedulers.background import BackgroundScheduler

    

def send_scheduled_whatsapp_message():
    """Send a reminder message on the 10th of every month."""
    recipient = os.getenv("RECIPIENT_WAID")  # Fetch recipient from environment
    
    if not recipient:
        logging.error("❌ No recipient phone number found! Skipping reminder.")
        return

    text = "Reminder: Your scheduled task for the 10th is due today!"

    try:
        message_data = get_text_message_input(recipient, text)
        response_code = send_message(message_data)

        if response_code == 200:
            print("xhdbihwdwihxw")
            logging.info(f"✅ Reminder successfully sent to {recipient}")
        else:
            logging.error(f"❌ Failed to send reminder. Response Code: {response_code}")

    except Exception as e:
        logging.error(f"❌ Error sending reminder: {str(e)}")

def reminder():
    print("inside")

    current_time = datetime.now()
    if hasattr(reminder, 'last_run'):
        if (current_time - reminder.last_run).total_seconds() < 60:  # 1 minute buffer
            logging.info("Skipping reminder execution - too soon since last run")
            return
    reminder.last_run = current_time
    logging.info("Reminder function triggered")
    logging.info(f"Reminder triggered at {datetime.now()}")
    clinet_reminders = get_clients_reminders()
    logging.info(f"Processing {len(clinet_reminders)} client reminders")

    for client_id, phone_number, sub_reminders, parent_reminder in clinet_reminders:
        logging.info(f"Processing client {client_id}, phone: {phone_number}, parent_reminder: {parent_reminder}")
        try:
            current_month = datetime.now().strftime("%B")
            current_date =  datetime.now().day
            if isinstance(sub_reminders, list) and sub_reminders:
                reminders_dict = sub_reminders[0]
                pending_tasks = [task for task, status in reminders_dict.items() if not status]
                logging.info(f"Pending tasks for {phone_number}: {pending_tasks}")

                if parent_reminder == "monthly" and pending_tasks:
                    if current_date  == 10 : # Get today's date (1-31)

                        text = f"Reminder: Tomorrow last date ‼️ Kindly submit {current_month}'s {', '.join(pending_tasks)}."

                        logging.info(f"Sending reminder to {phone_number}: {text}")
                        message_data = get_text_message_input(phone_number, text)
                        response_code = send_message(message_data)

                        if response_code == 200:
                            logging.info(f"✅ Reminder for {parent_reminder} successfully sent to {phone_number}")
                        else:
                            logging.error(f"❌ Failed to send {parent_reminder} reminder. Response Code: {response_code}")

                    elif current_date  == 11:
                        text = f"Reminder: Today is last date ❌  Kindly submit {current_month}'s {', '.join(pending_tasks)}."
                        logging.info(f"Sending reminder to {phone_number}: {text}")
                        message_data = get_text_message_input(phone_number, text)
                        response_code = send_message(message_data)

                        if response_code == 200:
                            logging.info(f"✅ Reminder for {parent_reminder} successfully sent to {phone_number}")
                        else:
                            logging.error(f"❌ Failed to send {parent_reminder} reminder. Response Code: {response_code}")
                    
                    #15th – 20th: GST Tax Payment Reminder 
                    elif current_date in ['15','16','17','18','19']:
                        text = f"Reminder: GST Tax Payment is due on {current_date} of {current_month}"
                        logging.info(f"Sending GST Tax Payment reminder to {phone_number}: {text}")
                        message_data = get_text_message_input(phone_number, text)
                        response_code = send_message(message_data)

                        if response_code == 200:
                            logging.info(f"✅ Reminder for GST Tax Payment successfully sent to {phone_number}")
                        else:
                            logging.error(f"❌ Failed to send GST Tax Payment reminder. Response Code: {response_code}")

                    elif current_date == 20:
                        text = f"URGENT❌: Today is the last day to pay GST tax for {current_month}"
                        logging.info(f"Sending reminder to {phone_number}: {text}")
                        message_data = get_text_message_input(phone_number, text)
                        response_code = send_message(message_data)

                        if response_code == 200:
                            logging.info(f"✅ Reminder for GST Tax Payment successfully sent to {phone_number}")
                        else:
                            logging.error(f"❌ Failed to send GST Tax Payment reminder. Response Code: {response_code}")


                    else:
                        text = f"Tesing Reminder: Kindly submit your pending documents {current_month}'s {', '.join(pending_tasks)}."
                        logging.info(f"Sending reminder to {phone_number}: {text}")
                        message_data = get_text_message_input(phone_number, text)
                        response_code = send_message(message_data)

                        if response_code == 200:
                            logging.info(f"✅ Reminder for {parent_reminder} successfully sent to {phone_number}")
                        else:
                            logging.error(f"❌ Failed to send {parent_reminder} reminder. Response Code: {response_code}")


        except json.JSONDecodeError:
            logging.error(f"❌ Error decoding JSON for client {client_id}: {sub_reminders}")
        except Exception as e:
            logging.error(f"❌ Error sending reminder: {str(e)}")


# def reminder():
#     """Schedule a reminder for the 10th of every month"""
    
#     clinet_reminders = get_clients_reminders()  # Fetch client_id, phone_number, sub_reminders, parent_reminder

#     for client_id, phone_number, sub_reminders, parent_reminder in clinet_reminders:
#         try:
#             current_month = datetime.now().strftime("%B")  # Get full month name (e.g., "March")

#             if isinstance(sub_reminders, list) and sub_reminders:
#                 reminders_dict = sub_reminders[0]  # Extract first dictionary from list
                
#                 # Filter out tasks that are False (pending)
#                 pending_tasks = [task for task, status in reminders_dict.items() if not status]

#                 if parent_reminder == "normal_gst_filers" and pending_tasks:
#                     text = f"Reminder: Kindly submit {current_month}'s {', '.join(pending_tasks)}."
                    
#                     message_data = get_text_message_input(phone_number, text)
#                     response_code = send_message(message_data)

#                     if response_code == 200:
#                         logging.info(f"✅ Reminder for {parent_reminder} successfully sent to {phone_number}")
#                     else:
#                         logging.error(f"❌ Failed to send {parent_reminder} reminder. Response Code: {response_code}")

#         except json.JSONDecodeError:
#             logging.error(f"❌ Error decoding JSON for client {client_id}: {sub_reminders}")

#         except Exception as e:
#             logging.error(f"❌ Error sending reminder: {str(e)}")



scheduler = BackgroundScheduler()
print("scheduler Started")
scheduler_id = id(scheduler)
logging.info(f"Scheduler initialized with ID: {scheduler_id}")
# scheduler.add_job(cleanup_inactive_sessions, 'interval', minutes=15)  # Remove the parentheses
# scheduler.add_job(reminder, 'interval', minutes=1, timezone="Asia/Kolkata")

# scheduler.add_job(reminder, 'cron', day=21, hour=17, minute=13, timezone="Asia/Kolkata")

# if not scheduler.get_job("cleanup_job"):
#         scheduler.add_job(cleanup_inactive_sessions, 'interval', minutes=15, id="cleanup_job")
#         logging.info("Cleanup job added to scheduler")

# if not scheduler.get_job("reminder_job"):
#     scheduler.add_job(reminder, 'cron', day=21, hour=17, minute=33, timezone="Asia/Kolkata", id="reminder_job")
    # scheduler.add_job(reminder, 'interval', minutes=1, timezone="Asia/Kolkata")

    # logging.info("Reminder job added to scheduler")

scheduler.add_job(reminder, 'cron', day=24, hour=18, minute=51, timezone="Asia/Kolkata", id="regular_reminder_job")

scheduler.add_job(reminder, 'cron', day=10, hour=10, minute=0, timezone="Asia/Kolkata", id="reminder_10")
scheduler.add_job(reminder, 'cron', day=11, hour=10, minute=0, timezone="Asia/Kolkata", id="reminder_11")




scheduler.start()
import logging
from fastapi.responses import JSONResponse
import json
import requests
import os
from datetime import datetime
from openai import OpenAI
# from app.services.openai_service import generate_response
import re

from dotenv import load_dotenv, set_key, find_dotenv


from app.config import load_configurations
settings = load_configurations()

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

# Replace the single data_history with a sessions dictionary
sessions = {}

# Define cleanup function before using it
def cleanup_inactive_sessions(timeout_minutes=30):
    """Remove sessions that have been inactive for more than timeout_minutes"""
    current_time = datetime.now()
    inactive_sessions = []
    
    for phone_number, session in sessions.items():
        last_activity = datetime.fromisoformat(session['last_activity'])
        if (current_time - last_activity).total_seconds() > timeout_minutes * 60:
            inactive_sessions.append(phone_number)
    
    for phone_number in inactive_sessions:
        del sessions[phone_number]
        logging.info(f"Cleaned up inactive session for {phone_number}")

# Initialize scheduler after defining the cleanup function
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_inactive_sessions, 'interval', minutes=15)  # Remove the parentheses
scheduler.start()

def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")


def get_text_message_input(recipient, text):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )


client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

sessions = {}

    # session state alone
# def generate_response(body):
#     phone_number = body['entry'][0]['changes'][0]['value']['contacts'][0]['wa_id']
#     user_name = body['entry'][0]['changes'][0]['value']['contacts'][0]['profile']['name']
#     message_body = body['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
#     message_id = body['entry'][0]['changes'][0]['value']['messages'][0]['id']

#     # Initialize session for new users
#     if phone_number not in sessions:
#         sessions[phone_number] = {
#             'name': user_name,
#             'last_message_id': message_id,
#             'state': 'name',
#             'data': {
#                 'phone_number': phone_number,
#                 'name': None,
#                 'email': None,
#                 'pan': None,
#                 'gstin': None,
#                 'service': None
#             },
#             'last_activity': datetime.now().isoformat()
#         }
#         return "Welcome! Please provide your full name."

#     # Update session with latest message
#     session = sessions[phone_number]
#     session['last_message_id'] = message_id
#     session['last_activity'] = datetime.now().isoformat()
    
#     current_message = message_body
    
#     # Handle different states of conversation
#     if session['state'] == 'name':
#         session['data']['name'] = current_message
#         session['state'] = 'email'
#         logging.info(f"Session updated for {phone_number}: {session}")
#         return "Please provide your email address."
        
#     elif session['state'] == 'email':
#         session['data']['email'] = current_message
#         session['state'] = 'pan'
#         logging.info(f"Session updated for {phone_number}: {session}")
#         return "Please provide your PAN number."
        
#     elif session['state'] == 'pan':
#         session['data']['pan'] = current_message
#         session['state'] = 'gstin'
#         logging.info(f"Session updated for {phone_number}: {session}")
#         return "Please provide your GSTIN (if applicable, or type 'NA')."
        
#     elif session['state'] == 'gstin':
#         session['data']['gstin'] = current_message
#         session['state'] = 'service'
#         logging.info(f"Session updated for {phone_number}: {session}")
#         return ("Please select a service category:\n"
#                "1. Income Tax\n"
#                "2. GST\n"
#                "3. Drafting\n"
#                "4. Registration\n"
#                "5. Loans\n"
#                "6. Other Services")
        
#     elif session['state'] == 'service':
#         service_options = {
#             "1": "Income Tax",
#             "2": "GST", 
#             "3": "Drafting",
#             "4": "Registration",
#             "5": "Loans",
#             "6": "Other Services"
#         }
        
#         if current_message in service_options:
#             session['data']['service'] = service_options[current_message]
#             session['state'] = 'complete'
#             logging.info(f"Session completed for {phone_number}: {session}")
#             print("-----------------total data---------------------",sessions)
#             return f"Thank you! We'll contact you soon regarding {service_options[current_message]} services."
#         else:
#             return "Please select a valid option (1-6)"

#     return "Thank you for your message."


    #llm + session state
def generate_response(body):  
    phone_number = body['entry'][0]['changes'][0]['value']['contacts'][0]['wa_id']
    user_name = body['entry'][0]['changes'][0]['value']['contacts'][0]['profile']['name']
    message_body = body['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
    message_id = body['entry'][0]['changes'][0]['value']['messages'][0]['id']

    service_mapping = {
        "1": "Income Tax (IT)",
        "2": "GST",
        "3": "Drafting",
        "4": "Registration",
        "5": "Loans",
        "6": "Other Services"
    }

    # Initialize session if not exists
    if phone_number not in sessions:
        sessions[phone_number] = {
            'user_name': user_name,
            'last_message_id': message_id,
            'state': 'name',
            'data': {
                'phone_number': phone_number,
                'name': None,
                'email': None,
                'pan': None,
                'gstin': None,
                'service': None
            },
            'last_activity': datetime.now().isoformat(),
            'last_question_asked_by_bot': "Welcome! Please provide your full name."
        }
        return "Welcome! Please provide your full name."
    
    session = sessions[phone_number]
    session['last_message_id'] = message_id
    session['last_activity'] = datetime.now().isoformat()
    
    # If the user selects a service by number, update the session
    if session['state'] == 'service' and session['data']['service'] is None and message_body.strip() in service_mapping:
        session['data']['service'] = service_mapping[message_body.strip()]
        session['state'] = 'completed'

    # Construct prompt

    print("---------------------------session state -----------------------------",session['state'])
    prompt = f"""
    You are a chatbot assistant managing a structured conversation flow for a WhatsApp bot.
    Your goal is to collect the required information from the user efficiently.
    
    The user has already provided the following details:
    {session['data']}
    
    Please follow these instructions:
    1. Ask only for missing or None fields in the following order: Name, Email, PAN, GSTIN, and Service.
    2. Ask each missing field in a direct, simple way (e.g., "Please provide your email").
    3. Once all fields are filled, confirm the user's service selection.
    4. Maintain conversation context and track progress within the session.
    5. Do NOT ask for already provided details.
    
    The user's current session state: {session['state']} 
    The last question asked by the bot is: "{session['last_question_asked_by_bot']}". Do not ask the same question again.
    The user's latest message: {message_body}
    
    When asking for service selection, provide the options in this structured format:
    
    *Services Required*  
    ✅ *Department Selection*  
    1️⃣ *Income Tax (IT)*  
    2️⃣ *GST*  
    3️⃣ *Drafting*  
    4️⃣ *Registration*  
    5️⃣ *Loans*  
    6️⃣ *Other Services*  
    
    Ask the user to select a service by entering the corresponding number.
    
    If all required details have been provided, respond with:  
    "Thank you! We have collected all the necessary details. We will verify and get back to you shortly."
    
    Do not validate the format of PAN, GSTIN, or email—just collect the input as provided.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful chatbot."},
            {"role": "user", "content": prompt}
        ]
    )

    bot_response = response.choices[0].message.content

    session['last_question_asked_by_bot'] = bot_response  

    # Update session state based on missing data
    if session['state'] == 'name' and session['data']['name'] is None:
        session['data']['name'] = message_body
        session['state'] = 'email'
    elif session['state'] == 'email' and session['data']['email'] is None:
        session['data']['email'] = message_body
        session['state'] = 'pan'
    elif session['state'] == 'pan' and session['data']['pan'] is None:
        session['data']['pan'] = message_body
        session['state'] = 'gstin'
    elif session['state'] == 'gstin' and session['data']['gstin'] is None:
        session['data']['gstin'] = message_body
        session['state'] = 'service'
    
    # If all fields are filled, send final confirmation
    if session['state'] == 'completed':
        bot_response = "Thank you! We have collected all the necessary details. We will verify and get back to you shortly."

    logging.info("***********************************************************************")
    logging.info("session: %s", sessions)
    logging.info("************************************************************************")
    
    return bot_response


session = {}
def generate_response(body):
    phone_number = body['entry'][0]['changes'][0]['value']['contacts'][0]['wa_id']
    user_name = body['entry'][0]['changes'][0]['value']['contacts'][0]['profile']['name']
    message_body = body['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
    message_id = body['entry'][0]['changes'][0]['value']['messages'][0]['id']
    
    # Initialize session only if it doesn't exist for this phone number
    if phone_number not in session:
        session[phone_number] = {"conversation_history": []}

    session[phone_number]["conversation_history"].append(f"User: {message_body}")
    
    # Append the new message to existing conversation history

    print("--------------------------------conversation_history---`-----------------------------",session)

    Step_by_step_prompt = f"""
        You are Ai Annamalai Associates.
        Greet with friendly tone.

        You guide users step by step, ensuring a smooth and engaging conversation while tracking conversation history to ask the next relevant question.

        Conversation History:  
        Refer to the conversation history to ask the next logical question based on the user's last response. Ensure the conversation flows logically without repeating questions.
        conversation_history: {session[phone_number]["conversation_history"]}

        current_user_message: {message_body}

        While providing a response to the user, sound like a human and use a professional tone. Do not return responses based on who said what.

        1. Step-by-Step Data Collection
            1. Ask for the user's name.
            2. Once the name is provided, ask for their email and validate the format. Ensure the email contains '@' and a valid domain (e.g., example@gmail.com, example@yahoo.com, example@outlook.com). Additionally, check for common domain name spelling errors (e.g., 'gamil.com' → 'gmail.com', 'yaho.com' → 'yahoo.com', 'outlok.com' → 'outlook.com') and suggest corrections if needed. If the email is invalid, prompt the user to enter a correct email format before proceeding."
            3. Ask whether they are an individual or a business.
            4. Based on their selection:
                1. If individual, request PAN (validate format).
                2. If business, request GSTIN (validate format).
            5. Confirm that the details have been recorded.

        2. Service Selection & Query Handling
            1. After collecting personal details, present the service list as follows:
                1. Income Tax (IT)
                2. GST
                3. Drafting
                4. Registration
                5. Loans
                6. Other Services
            2. In the same message, ask: "What do you want to know?"

        3. Step-by-Step Selection
            1. If the user chooses a service from the list, ask for specific details:
                1. For Income Tax Services:
                    1. Copy of IT Returns (specify Year)
                    2. Refund Status
                    3. Filing Status
                    4. TDS Payable
                    5. Income Tax Payable
                    6. TDS Filing Status
                    7. Reply to Notice Status
                    8. Reply to Appeal Status
                    9. Advance Tax Payable
                2. For GST Services:
                    1. Copy of GST Returns (specify Month & Year)
                    2. GST Return Filing Status
                    3. GST Refund Claim
                    4. GST Notice & Reply Status

        4. Once the user selects an option, do not ask any additional questions.
            1. Immediately summarize the entire details user provided and ask for confirmation: "Are these details correct?"
            2. If the user confirms or if they have already confirmed these details:
                - Do not ask for confirmation again.
                - Dont show sumarize details again and End with: "Thank you! We will get back to you shortly." alone.
            3. You must check for last line of conversation history. If the user response if **Yes or Correct** then you must end with: "Thank you! We will get back to you shortly." alone.
        
        Rules:
        1.Do not Say thank you or hello for every response.
        2.Do not ask any additional questions after the user said the service they want to know.
        3.Make sure every response is concise.
        4.Do not mention the format before the user provide the details.
        """
    

    nlp_prompt = f"""
        You are Ai Annamalai Associates.
        Greet with who you are and friendly tone.
        You guide users step by step, ensuring a smooth and engaging conversation while tracking conversation history to ask the next relevant question.

        Conversation History:  
        Refer to the conversation history to ask the next logical question based on the user's last response. Ensure the conversation flows logically without repeating questions.
        conversation_history: {session[phone_number]["conversation_history"]}

        current_user_message: {message_body}

        While providing a response to the user, sound like a human and use a professional tone. Do not return responses based on who said what.

        1. Step-by-Step Data Collection
        1. Ask for the user's name.
        2. Once the name is provided, ask for their email and validate the format."
        3. Ask whether they are an individual or a business.
        4. Based on their selection:
            1. If individual, request PAN (validate format).
            2. If business, request GSTIN (validate format).
        5. Confirm that the details have been recorded.

        2.Once user confirmed , present the service list as follows:
            1. Income Tax (IT)
            2. GST
            3. Drafting
            4. Registration
            5. Loans
            6. Other Services
        2. In the same message, ask: "What do you want to know?"

        3.Once user said the service they want to know 
            - Must -> (do not ask any additional questions or any other information, Do not ask necessary question or suggessions after that), 
            - immediately summarize the details and ask for confirmation: "Are these details correct?"

        4. If the user confirms or if they have already confirmed these details:
            - Do not ask for confirmation again.
            - End with: "Thank you! We will get back to you shortly."
        5. You must check for last line of conversation history. If the user response if **Yes or Correct** then you must send the  pdf file along with "Here are the details you have asked".Say thank you.       
        Rules:
        1.Do not Say thank you or hello for every response.
        2.Do not ask any additional questions after the user said the service they want to know.
        3.Make sure every response is concise.
        4.Do not mention the format before the user provide the details.                
          """    


    
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful chatbot."},
            {"role": "user", "content": nlp_prompt}
        ]
    )

    bot_response = response.choices[0].message.content

    session[phone_number]["conversation_history"].append(f"Bot: {bot_response}")

    return bot_response

def delete_uploaded_file(media_id,uploaded_time):

    print("------------------- delete_uploaded_file ------------------------")

    url = f"https://graph.facebook.com/{settings.VERSION}/{media_id}"
    
    headers = {
        "Authorization": f"Bearer {settings.ACCESS_TOKEN}"
    }

    response = requests.delete(url, headers=headers)

    deleted_time = datetime.now()#.strftime("%Y-%m-%d %H:%M:%S")

    total_deletion_time = deleted_time - uploaded_time

    print("---------------------- total_deletion_time -----------------------",total_deletion_time)

    if response.status_code == 200:
        print(f"--------------------- File{media_id} deleted from Meta Server.------------------------")
    else:
        print(f"-----------------------Failed to delete{media_id} file.----------------------------")



def send_message(data):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {settings.ACCESS_TOKEN}",
    }

    url = f"https://graph.facebook.com/{settings.VERSION}/{settings.PHONE_NUMBER_ID}/messages"

    try:
        logging.info("------------------- sending response ---------- %s",data)
        response = requests.post(
            url, data=data, headers=headers, timeout=10
        )  # 10 seconds timeout as an example
        response.raise_for_status() 

        return response.status_code
        
        # if response.status_code == 200 and data.get("document").get("id"):
        #     media_id = data.get("document").get("id")
        #     delete_uploaded_file(media_id)
             # Raises an HTTPError if the HTTP request returned an unsuccessful status code
    except requests.Timeout:
        logging.error("Timeout occurred while sending message")
        return JSONResponse(
            content={"status": "error", "message": "Request timed out"},
            status_code=408
        )
    except requests.RequestException as e:
        logging.error(f"Request failed due to: {e}")
        return JSONResponse(
            content={"status": "error", "message": "Failed to send message"},
            status_code=500
        )
    else:
        log_http_response(response)
        return JSONResponse(
            content={"status": "success", "message": "Message sent successfully"},
            status_code=response.status_code
        )


def process_text_for_whatsapp(text):
    # Remove brackets
    pattern = r"\【.*?\】"
    # Substitute the pattern with an empty string
    text = re.sub(pattern, "", text).strip()

    # Pattern to find double asterisks including the word(s) in between
    pattern = r"\*\*(.*?)\*\*"

    # Replacement pattern with single asterisks
    replacement = r"*\1*"

    # Substitute occurrences of the pattern with the replacement
    whatsapp_style_text = re.sub(pattern, replacement, text)

    return whatsapp_style_text


def get_document_message_input(recipient, media_id, caption=""):
    print("--------------- Entered into get_document_message_input -------------------- ")
    return json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "document",
        "document": {
            "id": media_id,
            "caption": caption,
            "filename": "GST Return Copy"
        }
    })

def send_document(phone_number, media_id, caption="",uploaded_time = None):
    print("--------------- inside send_docuent function -------------------- ")
    data = get_document_message_input(phone_number, media_id, caption)
    response_code = send_message(data)
    if response_code == 200 :
        delete_uploaded_file(media_id,uploaded_time)

    
    

def upload_doc_to_meta_cloud(document_path):
    print("-------------- Entered into upload_doc_to_meta_cloud function ----------------")

    headers = {
        "Authorization": f"Bearer {settings.ACCESS_TOKEN}"
    }
    url = f"https://graph.facebook.com/{settings.VERSION}/{settings.PHONE_NUMBER_ID}/media"

    # Determine the file type based on extension
    file_type = 'application/pdf'  # Since we're handling PDF files
    
    # Open file and send it to Meta API
    with open(document_path, 'rb') as file:
        files = {
            'file': ('document.pdf', file, file_type)
        }

        payload = {
            'messaging_product': 'whatsapp',
            'type': 'document'
        }    

        response = requests.post(url, files=files, data=payload, headers=headers)

        uploaded_time = datetime.now()

        if response.status_code == 200:
            media_id = response.json()['id']
            logging.info("File uploaded successfully. Media ID:%s", media_id)
            return media_id , uploaded_time
        else:
            logging.error("Failed to upload file:%s", response.text)
            return None


def process_whatsapp_message(body):
    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    
    # Handle different message types
    if message.get("type") == "text":
        message_body = message["text"]["body"]
        response = generate_response(body)
    elif message.get("type") == "audio":
        # Get audio details
        audio_id = message["audio"]["id"]
        mime_type = message["audio"]["mime_type"]
        
        # Download and process audio
        audio_url = get_media_url(audio_id)
        if audio_url:
            # Convert audio to text using speech-to-text service
            message_body = process_audio_to_text(audio_url)
            if message_body:
                # Process the transcribed text through your normal flow
                body["entry"][0]["changes"][0]["value"]["messages"][0]["text"] = {"body": message_body}
                response = generate_response(body)
            else:
                response = "I couldn't understand the audio message. Could you please type your message instead?"
        else:
            response = "Sorry, I couldn't process the audio message. Could you please type your message?"
    else:
        response = "I can only process text and voice messages. Please send your message in either format."


    # Check if this is a confirmation for GST copy returns
    if (message_body.lower() in ['yes', 'correct','yes correct','yes, correct'] and 
        wa_id in session and 
        any('gst return' in msg.lower() for msg in session[wa_id]["conversation_history"])):
        
        # Send the text response first
        print("--------------- Entered into document part-------------------- ")
        data = get_text_message_input(wa_id, response)
        send_message(data)
        
        # Then send the PDF document with a specific filename
        document_path = "C:\\Users\\SENA1\\Desktop\\Whatapp bot\\python-whatsapp-bot\\app\\utils\\copy_gst_returns_sample.pdf"
        filename = "GST_Returns_Copy.pdf"  # Specify your desired filename here

        media_id , uploaded_time = upload_doc_to_meta_cloud(document_path)

        send_document(wa_id, media_id, "Here is your GST return copy",uploaded_time)
    else:
        # Regular text message
        data = get_text_message_input(wa_id, response)
        send_message(data)

    # # Send response back to user
    # data = get_text_message_input(wa_id, response)
    # send_message(data)

def get_media_url(media_id):
    """Get the URL for downloading media content"""
    headers = {
        "Authorization": f"Bearer {settings.ACCESS_TOKEN}"
    }
    
    url = f"https://graph.facebook.com/{settings.VERSION}/{media_id}"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            media_data = response.json()
            return media_data.get("url")
    except Exception as e:
        logging.error(f"Error getting media URL: {e}")
    return None

def process_audio_to_text(audio_url):
    """Download and convert audio to text"""
    try:
        # Download the audio file
        headers = {
            "Authorization": f"Bearer {settings.ACCESS_TOKEN}"
        }
        audio_response = requests.get(audio_url, headers=headers)
        
        if audio_response.status_code == 200:
            # Save temporarily
            temp_file = "temp_audio.ogg" 
            with open(temp_file, "wb") as f:
                f.write(audio_response.content)
            
            try:
                # Use OpenAI Whisper API for speech-to-text
                with open(temp_file, "rb") as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file
                    )
                    return transcript.text
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    
    except Exception as e:
        logging.error(f"Error processing audio: {e}")
    return None

# def validate_phone_number(data):

#     # Replace these variables with your own values
#     access_token = settings.ACCESS_TOKEN
#     phone_number_id = settings.PHONE_NUMBER_ID
#     verification_method = 'SMS'  # or 'VOICE'
#     language_code = 'en_US'  # Language code for the verification message

#     # Step 1: Request a verification code
#     request_code_url = f'https://graph.facebook.com/v21.0/{phone_number_id}/request_code'
#     headers = {
#         'Authorization': f'Bearer {access_token}'
#     }
#     data = {
#         'code_method': verification_method,
#         'language': language_code
#     }

#     response = requests.post(request_code_url, headers=headers, data=data)
#     if response.status_code == 200:
#         print('Verification code sent successfully.')
#     else:
#         print(f'Failed to send verification code: {response.json()}')

#     # Step 2: Verify the code received by the user
#     verification_code = input('Enter the verification code received: ')
#     verify_code_url = f'https://graph.facebook.com/v21.0/{phone_number_id}/verify_code'
#     data = {
#         'code': verification_code
#     }

#     response = requests.post(verify_code_url, headers=headers, data=data)
#     if response.status_code == 200 and response.json().get('success'):
#         print('Phone number verified successfully.')
#         os.environ['is_Number_verified'] = True
#     else:
#         print(f'Failed to verify phone number: {response.json()}')



def is_valid_whatsapp_message(body):
    """
    Check if the incoming webhook event has a valid WhatsApp message structure.
    """
    # print("-------------------------------------------------------------------")
    # print("Entered ""is_valid_whatsapp_message"" ------body--> ",body)
    # print("-------------------------------------------------------------------")

    ph_no = body['entry'][0]['changes'][0]['value']['contacts'][0]['wa_id']

    os.environ['RECIPIENT_WAID'] = ph_no

    set_key(dotenv_path, 'RECIPIENT_WAID', ph_no)



    print("current user number",os.environ['RECIPIENT_WAID'])

    # validate_phone_number(body)



    return (
        body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
        and body["entry"][0]["changes"][0]["value"]["messages"][0]
    )

def is_session_expired(phone_number, timeout_minutes=30):
    if phone_number not in sessions:
        return True
    
    last_activity = datetime.fromisoformat(sessions[phone_number]['last_activity'])
    return (datetime.now() - last_activity).total_seconds() > timeout_minutes * 60

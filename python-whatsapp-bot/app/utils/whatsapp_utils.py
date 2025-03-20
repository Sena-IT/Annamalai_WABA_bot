import logging
from fastapi.responses import JSONResponse
import json
import requests
import os
from datetime import datetime
from openai import OpenAI
# from app.services.openai_service import generate_response
import re
from pydantic import BaseModel
from typing import Dict, List, Optional

from dotenv import load_dotenv, set_key, find_dotenv

#database
from .database import insert_client , insert_srn , get_client_by_phone


from app.config import load_configurations
settings = load_configurations()

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

# Replace the single data_history with a sessions dictionary
sessions = {}

# Define cleanup function before using it
def cleanup_inactive_sessions(timeout_minutes=5):
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
            logging.info(f"✅ Reminder successfully sent to {recipient}")
        else:
            logging.error(f"❌ Failed to send reminder. Response Code: {response_code}")

    except Exception as e:
        logging.error(f"❌ Error sending reminder: {str(e)}")


# Initialize scheduler after defining the cleanup function 
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_inactive_sessions, 'interval', minutes=15)  # Remove the parentheses
scheduler.add_job(send_scheduled_whatsapp_message, 'cron', day=14, hour=22, minute=17, timezone="Asia/Kolkata")

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


class SessionData(BaseModel):
    name: Optional[str]
    aadhar_number: Optional[str]
    aadhar_number_validated: bool
    email: Optional[str]
    email_validated: bool
    pan: Optional[str]
    pan_validated: bool
    gstin: Optional[str]
    gstin_validated: bool
    service: Optional[str]
    service_confirmation: bool
    sub_service: Optional[str]

class Session(BaseModel):
    user_name: str
    last_message_id: str
    state: str
    data: SessionData
    llm_response: Optional[str]
    conversation_history: List[str]

class Sessions(BaseModel):
    sessions: Dict[str, Session]  # Phone number as the key



    #llm + session state
def generate_response(body):  
    phone_number = body['entry'][0]['changes'][0]['value']['contacts'][0]['wa_id']
    user_name = body['entry'][0]['changes'][0]['value']['contacts'][0]['profile']['name']
    message_body = body['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
    message_id = body['entry'][0]['changes'][0]['value']['messages'][0]['id']

    # Initialize session if not exists
    if phone_number not in sessions:
        sessions[phone_number] = {
            'user_name': user_name,
            'last_message_id': message_id,
            'state': 'name',
            'data': {
                'phone_number': phone_number,
                'name': None,
                'aadhar_number':None,
                'aadhar_number_validated' : False,
                'email': None,
                'email_validated': False,
                'pan': None,
                'pan_validated': False,
                'gstin': None,
                'gstin_validated': False,
                'service': None,
                'service_confirmation': False,
                'sub_service': None
            },
            'llm_response': None,
            'conversation_history':[]
                }
        
    sessions[phone_number]['conversation_history'].append(f"User: {message_body}")



  


        
    def all_chars_same(s: str) -> bool:
        """Check if all characters in the string are the same."""
        return s == s[0] * len(s)

    def validate_session_data(session_data):
        """Validate multiple fields from session data and update validation status."""

        validation_messages = []

        # Validate Aadhaar
        if session_data.get("aadhar_number") and session_data.get("aadhar_number_validated") is False:
            print("---------- aadhar validation----------------")
            aadhar = session_data.get("aadhar_number")
            if not re.match(r'^\d{12}$', aadhar):
                validation_messages.append("❌ Aadhaar number must be exactly 12 digits.")
                sessions[phone_number]['data']['aadhar_number'] = None
            elif all_chars_same(aadhar):
                validation_messages.append("❌ Aadhaar number cannot have all identical digits (e.g., 111111111111).")
                sessions[phone_number]['data']['aadhar_number'] = None
            else:
                print("---------- aadhar validation-----True-----------")
                sessions[phone_number]['data']["aadhar_number_validated"] = True  # Mark as valid

        # Validate Email
        if session_data.get("email") and session_data.get("email_validated") is False:
            print("---------- email validation----------------")
            email = session_data.get("email")
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_regex, email):
                validation_messages.append("❌ Invalid email format. Example: user@example.com")
                sessions[phone_number]['data']['email'] = None
            else:
                local_part = email.split('@')[0]  # Check only the part before '@'
                if all_chars_same(local_part):
                    validation_messages.append("❌ Email local part cannot have all identical characters (e.g., aaaaaaa@aaa.com).")
                    sessions[phone_number]['data']['aadhar_number'] = None
                else:
                    print("---------- email validation-----True-----------")
                    session_data["email_validated"] = True  # Mark as valid

        # Validate PAN
        if session_data.get("pan") and session_data.get("pan_validated") is False:
            print("----------inside pan----------------")
            pan = session_data.get("pan")
            if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', pan):
                validation_messages.append("❌ PAN must be in format: ABCDE1234F (5 uppercase letters, 4 digits, 1 uppercase letter).")
                sessions[phone_number]['data']['pan'] = None
            elif all_chars_same(pan):
                validation_messages.append("❌ PAN cannot have all identical characters (e.g., AAAAAAAAAA).")
                sessions[phone_number]['data']['pan'] = None
            else:
                print("---------- pan validation-----True-----------")
                session_data["pan_validated"] = True  # Mark as valid

        # Validate GSTIN
        if session_data.get("gstin") and session_data.get("gstin_validated") is False:
            print("---------- gstin----------------")
            gstin = session_data.get("gstin")
            if not re.match(r'^\d{2}[A-Z0-9]{10}[0-9]Z[A-Z0-9]$', gstin):
                validation_messages.append("❌ GSTIN must be 15 characters: 2 digits, 10 alphanumeric, 1 digit, 'Z', and 1 alphanumeric.")
                sessions[phone_number]['data']['gstin'] = None
            elif all_chars_same(gstin):
                validation_messages.append("❌ GSTIN cannot have all identical characters (e.g., 111111111111111).")
                sessions[phone_number]['data']['gstin'] = None
            else:
                print("---------- gstin validation-----True-----------")
                session_data["gstin_validated"] = True  # Mark as valid

        return "\n".join(validation_messages) if validation_messages else "valid"  # Return all validation errors
        
    new_prompt = f"""
        You are ai assistant for Annamalai Associates.
        Greet with who you are and friendly tone.
        You guide users step by step, ensuring a smooth and engaging conversation while tracking conversation history to ask the next relevant question.
        **You must always return a response in llm_response JSON parameter, never return it as null value**                

        this is the session  data : {sessions[phone_number]}

        Each llm response has to be updated in {sessions[phone_number]['llm_response']} and return the session data in proper json format.

        Conversation History:  
        Refer to the conversation history fully to ask the next logical question based on the user's last response.
        Ensure the conversation flows logically without repeating questions.
        conversation_history: {sessions[phone_number]["conversation_history"]}

        current user message : {message_body}

        Refer to the user query properly and ask accordingly.

        While providing a response to the user, sound like a human and use a professional tone. Do not return responses based on who said what.

        1. Step-by-Step Data Collection
            1. Start by introducing yourself and present the Parent service list in number format:
                1. Income_Tax
                2. GST  
                3. Drafting
                4. Registration
                5. Loans
                6. Other_Services
            2. In the same initial message, ask below details
                - The user's name
                - Their email , email validation,
                - Their aadhar number ,
                - Whether they are an individual or a business
                - Which service they're interested in
            3. Once user provided the initial message you need to extract these below deatils from user natural language input.
                - PAN
                - Emailid
                - GSTIN number
                - Phone number
                - Aadhar number

                Update the extracted details in session[phone_number]['data'].               


            3. Once they provide this information, based on their individual/business selection:
                1. If individual, request PAN   
                2. If business, request GSTIN             
            4. Confirm that all details have been recorded.

        2. Once all details are collected, immediately summarize the information and ask for confirmation: "Are these details correct?"

        3. If the user confirms , do not send summary again , only return the service they asked and confirmation as true or false in json.
        
        4. You must check for last line of conversation history. If the user response is **Yes or Correct** then you must return only the related Parent "{sessions[phone_number]['data']['service']}  like GST , Income_Tax etc.. , {sessions[phone_number]['data']["service_confirmation"]} as true or false , {sessions[phone_number]['data']["sub_service"]} : "exact service query user asked"  in json alone .
        
        5. Must Once confimed , after ask if they want any service. do not give that json file again if user asks any futher unrelated questions.
        
        6. If they say thank , say regardingly.

        Rules:
        1. Analyze the json provided and ask the next question in 'llm_response' tag in the above JSON format, Please answer question using current user message.
         1.1 Every final respnse must return in json format of session data.
        2. Do not update the validation results to be true , its default to be false.
        3. Must Make sure every response is concise.
        4. Do not mention the format before the user provides the details.
        5. do not ask the user details again and again after they submitted also.
        6. Must - If any format is wrong , ask them to enter it correctly. Do not show the pattern to them.
        7. Do not show the services everytime.
        8. Do not hallucinate.
        9. Do not ask any additional questions after collecting all required information.
        10. update the session data with the user response if its related with key value.
        11. If already the data is existed in the 

        You must return only is JSON format. you must not include anyother extra words in the response.
    """

    new_prompt_1 = f"""
        You are an AI assistant for Annamalai Associates.
        Greet the user warmly and professionally, introducing yourself.
        Guide users step-by-step through a smooth conversation, tracking responses to ask the next relevant question.
        **Always include a response in 'llm_response'—never leave it null.**

        Session data: {sessions[phone_number]}

        Update each response in {sessions[phone_number]['llm_response']} and return the full session data in JSON format.

        Use conversation history {sessions[phone_number]["conversation_history"]} to determine the next logical question based on the user’s last response.

        Current user message: {message_body}

        Respond appropriately in a human-like, professional tone.

        ### How to Collect Information:
        1. **Initial Greeting and Data Collection in single messagge:**
           - In one message:
             - List Parent services:
               1. Income_Tax
               2. GST  
               3. Drafting
               4. Registration
               5. Loans
               6. Other_Services
             - Ask for:
               - Name
               - Email
               - Aadhar number
               - Individual or business
               - Which service they are interesting in

        2. **Extract Details:**
           - From user’s reply, pull out:
             - PAN
             - GSTIN
             - Phone number
           - Store in {sessions[phone_number]['data']}.

        3. **Follow-Up:**
           - Individual: only Request PAN.
           - Business: only Request GSTIN.
           - Confirm details recorded.

        4. **Summarize:**
           - After collecting all, Show the summarized details and ask: "Are these details correct?"

        5. **Confirmation:**
           -   If user give confirmation keywords like "Yes","yep", "Correct," set {sessions[phone_number]['llm_response']} to "confirmed" and return Parent service like GST in {sessions[phone_number]['data']["service"]}, {sessions[phone_number]['data']["service_confirmation"]} as true/false, and Exact service user asked in {sessions[phone_number]['data']["sub_service"]} in JSON.
        6. **Post-Confirmation:**
           - Ask if they need help with a service.

        7. **Closure:**
           - If "thank you," reply courteously.

        ### Rules:
        1. Keep validation fields false by default and Do not update true its not your job.
        2. Keep responses concise.
        3. Don’t explain format unless asked.
        4. Don’t repeat questions after details are provided.
        5. If a detail is wrong, ask to correct it without showing the pattern.
        6. Don’t repeat service list after initial message.
        7. Stick to facts.
        8. Stop asking once all details are collected.
        9. Update session data only with relevant key-value responses.
        10. Make sure the response your are giving is in proper structure like use bulletins whenever need.

        ### Output:
        - Return JSON with updated session data.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful chatbot."},    
            {"role": "user", "content": new_prompt_1}
        ],
    )

    bot_response = response.choices[0].message.content

    print("&&&&&&&&&&&&&&&&&&& bot response &&&&&&&&&&&&&&&&&&&&&&& ",bot_response)

    json_match = re.search(r'\{.*\}', bot_response, re.DOTALL)
    
    if json_match:

        response_json = json.loads(json_match.group())

    sessions[phone_number]["data"].update(response_json['data'])


    # data validation 
    session_data = sessions[phone_number]['data']
    print("session_data",session_data)
    validation_response = validate_session_data(session_data)

    if validation_response != "valid" :

        sessions[phone_number]['conversation_history'].append(f"bot: {validation_response}")

        return validation_response
    


    sessions[phone_number]['conversation_history'].append(f"bot: {response_json['llm_response']}")
   
   
    return response_json['llm_response']


def delete_uploaded_file(media_id,uploaded_time):

    print("------------------- delete_uploaded_file ------------------------")

    url = f"https://graph.facebook.com/{settings.VERSION}/{media_id}"
    
    headers = {
        "Authorization": f"Bearer {settings.ACCESS_TOKEN}"
    }

    response = requests.delete(url, headers=headers)

    deleted_time = datetime.now()
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
        # insert_client(session[phone_number]['data'],phone_number)
    return response_code
       
            

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
            return None , None


def get_audio_message_input(recipient, media_id):
    """Create audio message input format for WhatsApp API"""
    return json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "audio",
        "audio": {
            "id": media_id
        }
    })

def convert_text_to_speech(text):
    """Convert text to speech using OpenAI's TTS API"""
    try:
        speech_file_path = "temp_speech.mp3"
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",  # You can choose from: alloy, echo, fable, onyx, nova, shimmer
            input=text
        )
        
        # Save the audio file using the recommended streaming approach
        with open(speech_file_path, 'wb') as file:
            for chunk in response.iter_bytes():
                file.write(chunk)
        return speech_file_path
    except Exception as e:
        logging.error(f"Error in text-to-speech conversion: {e}")
        return None

def upload_audio_to_meta_cloud(audio_path):
    """Upload audio file to Meta's cloud storage"""
    print("-------------- Uploading audio to Meta cloud ----------------")

    headers = {
        "Authorization": f"Bearer {settings.ACCESS_TOKEN}"
    }
    url = f"https://graph.facebook.com/{settings.VERSION}/{settings.PHONE_NUMBER_ID}/media"
    
    with open(audio_path, 'rb') as file:
        files = {
            'file': ('audio.mp3', file, 'audio/mpeg')
        }
        
        payload = {
            'messaging_product': 'whatsapp',
            'type': 'audio'
        }    

        response = requests.post(url, files=files, data=payload, headers=headers)
        uploaded_time = datetime.now()

        if response.status_code == 200:
            media_id = response.json()['id']
            logging.info("Audio uploaded successfully. Media ID: %s", media_id)
            return media_id, uploaded_time
        else:
            logging.error("Failed to upload audio: %s", response.text)
            return None, None

def send_audio_response(wa_id, text_response):
    """Convert text to speech and send as audio message"""
    try:
        # Convert text to speech
        audio_path = convert_text_to_speech(text_response)
        if not audio_path:
            return False

        # Upload audio to Meta cloud
        media_id, uploaded_time = upload_audio_to_meta_cloud(audio_path)
        if not media_id:
            return False

        # Send audio message
        data = get_audio_message_input(wa_id, media_id)
        response_code = send_message(data)
        
        # Clean up
        if os.path.exists(audio_path):
            os.remove(audio_path)
        
        if response_code == 200:
            delete_uploaded_file(media_id, uploaded_time)
            return True
            
        return False
    except Exception as e:
        logging.error(f"Error sending audio response: {e}")
        return False
    

def update_session_data(phone_number,response_dict):
    conversation_extract_prompt = f"""
                            Extract all user information from this conversation history into a structured format:
                            {session[phone_number]["conversation_history"]}
                            
                            Extract and return ONLY a JSON object with these fields:
                            {{
                                "name": "user's name from conversation",
                                "email": "user's email from conversation",
                                "aadhar_number" : :"user's aadhar from conversation"
                                "type": "Individual or Business from conversation",
                                "pan": "PAN if Individual",
                                "gstin": "GSTIN if Business",
                                "service": "{response_dict.get('service', '')}",
                                "service_specific_data": "{response_dict.get('sub_service','')}"
                            }}
                            """

    # Get structured data from conversation
    extract_response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Extract user information into JSON format only."},
            {"role": "user", "content": conversation_extract_prompt}
        ]
    )

    # Process the extraction response
    extract_text = extract_response.choices[0].message.content
    print("extract_text\n",extract_text)

    json_match = re.search(r'\{.*\}', extract_text, re.DOTALL)
    print("json_match",json_match)
    if json_match:
        extracted_data = json.loads(json_match.group())
        print("extracted_json\n",extracted_data)
        # Update session data
        session[phone_number]["data"].update(extracted_data)
        print("Updated session data:\n\n", session)  

    if not get_client_by_phone(phone_number) :
        
        insert_client(session[phone_number]['data'],phone_number)



def process_whatsapp_message(body):
    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    phone_number = body['entry'][0]['changes'][0]['value']['contacts'][0]['wa_id']

    print("----------------------body---------------------",body)
    
    # Handle different message types
    if message.get("type") == "text":
        message_body = message["text"]["body"]
        response = generate_response(body)
    elif message.get("type") == "audio":
        audio_id = message["audio"]["id"]
        audio_url = get_media_url(audio_id)
        if audio_url:
            message_body = process_audio_to_text(audio_url)
            if message_body:
                body["entry"][0]["changes"][0]["value"]["messages"][0]["text"] = {"body": message_body}
                response = generate_response(body)
            else:
                response = "I'm having trouble processing your voice message right now. Could you please either try sending the voice message again or type your message? This will help ensure I understand your request correctly."
        else:
            response = "I'm unable to access the voice message at the moment. Please try sending your message as text instead."
    else:
        response = "I can only process text and voice messages. Please send your message in either format."


    # data = get_text_message_input(wa_id, response)
    # send_message(data)
    
    try:
        print("----------------------bot response--------------",response)
        if sessions[phone_number]['data']["service_confirmation"]:
        # session_data = sessions[phone_number]['data']
            if sessions[phone_number]['data']["service"] == 'GST' and sessions[phone_number]['data']["service_confirmation"]:
                if not get_client_by_phone(phone_number) :
                    insert_client(sessions[phone_number]['data'],phone_number)  #inserting client details into db
                service_type = sessions[phone_number]['data']["service"]

                document_path = "C:\\Users\\SENA1\\Desktop\\Whatapp bot\\python-whatsapp-bot\\app\\utils\\copy_gst_returns_sample.pdf"
                if document_path:
                    media_id, uploaded_time = upload_doc_to_meta_cloud(document_path)
                    if media_id:
                        uploaded_status=send_document(wa_id, media_id, f"Here is your {service_type} document", uploaded_time)
                        if uploaded_status == 200:
                            
                            sessions[phone_number]['data']['status'] = 'completed'
                            print("++++++++++++++++inside gst insert++++++++++++++++++")
                            insert_response , srn_id =insert_srn(sessions[phone_number]['data'],phone_number)
                            if insert_response == 201 :
                                message=f"✅ SRN ({srn_id}) created successfully for the service : "+ sessions[phone_number]['data']['sub_service']
                                data = get_text_message_input(wa_id,message)
                                send_message(data)
                                return

            else:
                print("++++++++++++++++inside other service insert++++++++++++++++++")
                insert_response,srn_id=insert_srn(sessions[phone_number]['data'],phone_number) #default status pending
                if insert_response == 201 :
                    message=f"✅ SRN ({srn_id}) created successfully for the service : "+ sessions[phone_number]['data']['sub_service']
                    data = get_text_message_input(wa_id,message)
                    send_message(data)
                    return
        
        else:
                    # Send both text and audio response
            data = get_text_message_input(wa_id, response)
            send_message(data)
            # send_audio_response(wa_id, response)
            
    except Exception as e:
        logging.error(f"Error processing message: {str(e)}")
        fallback_message = "Sorry, I encountered an error processing your request."
        data = get_text_message_input(wa_id, fallback_message)
        send_message(data)

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
            print("media url: ", media_data.get("url"))
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
        audio_response = requests.get(audio_url, 
                                        headers=headers , 
                                        timeout=60,  # 30 seconds timeout
                                        verify=True )
        
        print("$$$$$$$$$$$$$ audio_response",audio_response)
        
        if audio_response.status_code == 200:
            # Save temporarily
            temp_file = f"temp_audio{datetime.now().timestamp()}.ogg" 
            
            try:
                with open(temp_file, "wb") as f:
                    f.write(audio_response.content)
            
            
                # Use OpenAI Whisper API for speech-to-text
                with open(temp_file, "rb") as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        timeout=60
                    )
                    return transcript.text

            except Exception as whisper_error:
                        logging.error(f"Whisper API error: {whisper_error}")
                        return None 
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    
        else:
            logging.error(f"Failed to download audio. Status code: {audio_response.status_code}")
            return None

    except requests.Timeout:
        logging.error("Timeout while downloading audio file")
        return None
    except requests.ConnectionError:
        logging.error("Connection error while downloading audio file")
        return None
    except Exception as e:
        logging.error(f"Error processing audio: {str(e)}")
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

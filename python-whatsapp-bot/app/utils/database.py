import os

import logging
from datetime import datetime
from dotenv import load_dotenv, find_dotenv
import json
import psycopg2

# Load Environment Variables
dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

# Database Connection
import psycopg2
db_conn = psycopg2.connect(
    host=os.getenv('DB_HOST'),
    port=os.getenv('DB_PORT'),
    database=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD')
)

# ===========================
# ✅ Client Operations
# ===========================

def insert_client(data, phone_number):
    """
    Insert client data into the clients table.
    """
    cursor = None
    try:
        # Validate required fields
        if not data.get('name'):
            logging.error("❌ Client name is required")
            return False
            
        query = """
            INSERT INTO clients (name, aadhar_number, phone_number, authorized_phone_numbers, 
            aadhar_verified, phone_number_verified, pan, pan_verified, gstin, gstin_verified, 
            email, email_validated, aadhar_number_validated, pan_validated, gstin_validated, client_type, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (phone_number) DO UPDATE 
            SET name = EXCLUDED.name,
                aadhar_number = EXCLUDED.aadhar_number,
                authorized_phone_numbers = EXCLUDED.authorized_phone_numbers,
                aadhar_verified = EXCLUDED.aadhar_verified,
                phone_number_verified = EXCLUDED.phone_number_verified,
                pan = EXCLUDED.pan,
                pan_verified = EXCLUDED.pan_verified,
                gstin = EXCLUDED.gstin,
                gstin_verified = EXCLUDED.gstin_verified,
                email = EXCLUDED.email,
                email_validated = EXCLUDED.email_validated,
                aadhar_number_validated = EXCLUDED.aadhar_number_validated,
                pan_validated = EXCLUDED.pan_validated,
                gstin_validated = EXCLUDED.gstin_validated,
                client_type = EXCLUDED.client_type
            RETURNING client_id
        """
        
        values = (
            data.get('name'),
            data.get('aadhar_number'),
            phone_number,
            json.dumps(data.get('authorized_phone_numbers', [])),
            data.get('aadhar_verified', False),
            data.get('phone_number_verified', False),
            data.get('pan'),
            data.get('pan_verified', False),
            data.get('gstin'),
            data.get('gstin_verified', False),
            data.get('email'),
            data.get('email_validated', False),
            data.get('aadhar_number_validated', False),
            data.get('pan_validated', False),
            data.get('gstin_validated', False),
            data.get('client_type')  # Fixed column name
        )
        
        cursor = db_conn.cursor()
        cursor.execute(query, values)
        client_id = cursor.fetchone()[0]
        db_conn.commit()
        logging.info("✅ Client inserted/updated successfully with ID: %s", client_id)
        return True
        
    except psycopg2.Error as e:
        if db_conn:
            db_conn.rollback()
        logging.error("❌ Error inserting client: %s", e)
        return False
        
    finally:
        if cursor:
            cursor.close()

def get_client_by_phone(phone_number):
    """
    Fetch client details by phone number, including validation fields.
    """
    query = """
        SELECT client_id, name, aadhar_number, phone_number, authorized_phone_numbers, 
               pan, pan_verified, gstin, gstin_verified, client_type, email, 
               email_validated, aadhar_number_validated, pan_validated, gstin_validated,
               aadhar_verified, phone_number_verified, created_at
        FROM clients
        WHERE phone_number = %s
    """
    with db_conn.cursor() as cursor:
        cursor.execute(query, (phone_number,))
        result = cursor.fetchone()
        if result:
            return {
                "client_id": result[0],
                "name": result[1],
                "aadhar_number": result[2],
                "phone_number": result[3],
                "authorized_phone_numbers": result[4],
                "pan": result[5],
                "pan_verified": result[6],
                "gstin": result[7],
                "gstin_verified": result[8],
                "client_type": result[9],
                "email": result[10],
                "email_validated": result[11],
                "aadhar_number_validated": result[12],
                "pan_validated": result[13],
                "gstin_validated": result[14],
                "aadhar_verified": result[15],  # Added missing field
                "phone_number_verified": result[16],  # Added missing field
                "created_at": result[17]  # Added missing field
            }
        return None
    

def upload_document(documents):
    """Uploads document submission details into the database with a single query."""
    
    query = """
        INSERT INTO documents_submission(client_id, reminder_id, year, month, documents_submitted)
        VALUES (
            (SELECT client_id FROM masterClientTable WHERE gstin = %s),
            %s, %s, %s, %s
        )
        RETURNING client_id;
    """

    try:
        # Establish database connection
        db_conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )

        with db_conn.cursor() as cursor:
            # Execute the query
            cursor.execute(query, (
                documents.gstin,
                1,
                documents.year,
                documents.month,
                json.dumps(documents.documents)  # Convert list to JSON
            ))

            result = cursor.fetchone()
            if not result:
                print(f"Client with GSTIN {documents.gstin} not found.")
                return {"status": 404, "message": f"Client with GSTIN {documents.gstin} not found."}

        db_conn.commit()
        print("Document uploaded successfully")
        return {"status": 200, "message": "Documents inserted successfully"}

    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return {"status": 500, "message": f"Database operation failed: {str(e)}"}

    finally:
        db_conn.close()
    

    
# ===========================
# ✅ SRN Operations
# ===========================
def get_latest_srn_number():
    """
    Get the latest SRN number for the current month and year
    """
    current_date = datetime.now()
    month_year_prefix = current_date.strftime("%m%y")
    
    query = """
        SELECT srn_id FROM srn 
        WHERE srn_id LIKE %s 
        ORDER BY srn_id DESC LIMIT 1
    """
    
    with db_conn.cursor() as cursor:
        cursor.execute(query, (f"{month_year_prefix}%",))
        result = cursor.fetchone()
        
        if result:
            # Extract the numeric part and increment
            last_number = int(result[0][-4:])
            return last_number + 1
        return 1

def insert_srn(session_data, phone_number):
    """
    Insert SRN data into srns table.
    """
    cursor = None
    try:
        client = get_client_by_phone(phone_number)
        print("------------insert srn---- client ---------", client)
        if not client:
            logging.error("❌ Client not found for phone number: %s", phone_number)
            return
            
        client_id = client['client_id']
        
        cursor = db_conn.cursor()
        
        # Generate SRN ID
        current_date = datetime.now()
        month_year_prefix = current_date.strftime("%m%y")
        next_number = get_latest_srn_number()
        srn_id = f"{month_year_prefix}{next_number:04d}"
        
        # Fetch the service_id based on the service_name
        service_name = session_data.get('service', 'GST')
        service_id_query = "SELECT service_id FROM service WHERE service_name = %s"
        cursor.execute(service_id_query, (service_name,))
        service_id_result = cursor.fetchone()

        print("session data insert srn",session_data)
        
        if not service_id_result:
            logging.error("❌ Service ID not found for service_name '%s'.", service_name)
            return
            
        service_id = service_id_result[0]
        
        # Modified query to include srn_id
        query = """
            INSERT INTO srn (srn_id, client_id, service_id, due_date, task_type, status, 
            payment_status, service_specific_data, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        values = (
            srn_id,
            client_id,
            service_id,
            session_data.get('due_date', None),
            session_data.get('task_type', "non-recurring"),
            session_data.get('status' , "pending"),
            session_data.get('payment_status','unpaid'),
            json.dumps(session_data.get('sub_service', {}))
        )
        
        cursor.execute(query, values)
        db_conn.commit()
                
        if cursor.rowcount > 0:
            logging.info("✅ SRN inserted successfully with ID: %s", srn_id)
            status_code = 201
        else:
            logging.warning("⚠️ No rows affected.")
            status_code = 400
        return status_code , srn_id
                
    except Exception as e:
        if db_conn:
            db_conn.rollback()
        logging.error("❌ Error inserting SRN: %s", str(e))
        
    finally:
        if cursor:
            cursor.close()


def get_srn_by_client(client_id):
    """
    Fetch all SRNs for a client.
    """
    query = """
        SELECT srn_id, service_id, due_date, task_type, status, payment_status
        FROM srns
        WHERE client_id = %s
    """
    with db_conn.cursor() as cursor:
        cursor.execute(query, (client_id,))
        results = cursor.fetchall()
        return [
            {
                "srn_id": row[0],
                "service_id": row[1],
                "due_date": row[2],
                "task_type": row[3],
                "status": row[4],
                "payment_status": row[5]
            }
            for row in results
        ]


# ===========================
# ✅ Payment Operations
# ===========================
def insert_payment(data):
    """
    Insert payment data into payments table.
    """
    query = """
        INSERT INTO payments (client_id, srn_id, amount, payment_method, 
        payment_status, transaction_id, paid_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
    """
    values = (
        data.get('client_id'),
        data.get('srn_id'),
        data.get('amount'),
        data.get('payment_method'),
        data.get('payment_status'),
        data.get('transaction_id')
    )
    
    with db_conn.cursor() as cursor:
        cursor.execute(query, values)
        db_conn.commit()
        logging.info("✅ Payment inserted successfully.")


# ===========================
# ✅ Service Operations
# ===========================
def insert_service(data):
    """
    Insert service data into services table.
    """
    query = """
        INSERT INTO services (service_name, description, sub_services, created_at)
        VALUES (%s, %s, %s, NOW())
    """
    values = (
        data.get('service_name'),
        data.get('description'),
        json.dumps(data.get('sub_services'))
    )
    
    with db_conn.cursor() as cursor:
        cursor.execute(query, values)
        db_conn.commit()
        logging.info("✅ Service inserted successfully.")


# ===========================
# ✅ Close DB Connection
# ===========================
def close_db_connection():
    db_conn.close()


import atexit
atexit.register(close_db_connection)

def get_clients_reminders():
    """Fetch clients with their phone numbers, sub_reminders, and parent_reminder."""
    
    query = """
        SELECT c.client_id, c.phone_number, rs.sub_reminders, rs.parent_reminder
        FROM clients c
        JOIN recurring_service rs ON c.client_id = rs.client_id;
    """
    
    try:
        with db_conn.cursor() as cursor:
            cursor.execute(query)
            results = cursor.fetchall()
            return results  # Returns a list of tuples (client_id, phone_number, sub_reminders, parent_reminder)
    
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return []    
    

def get_client_reminders_gstin(gstin):
    """Fetch client reminders for a specific GSTIN."""

    query = """
        SELECT c.client_id, c.phone_number, rs.sub_reminders, rs.parent_reminder
        FROM clients c
        JOIN recurring_service rs ON c.client_id = rs.client_id
        WHERE c.gstin = %s
    """

    try:
        db_conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )
        with db_conn.cursor() as cursor:
            cursor.execute(query, (gstin,))  # Pass parameters as a tuple
            results = cursor.fetchall()
            print(results)
            return results  # Returns a list of tuples

    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return []
     
    finally:
        db_conn.close()

def get_client_reminder_details(gstin):
    """Fetch client reminder details for a specific GSTIN."""
    
    query = """
        SELECT c.client_id, c.phone_number, ds.documents_submitted, ds.year , ds.month
        FROM masterClientTable c
        JOIN documents_submission ds ON c.client_id = ds.client_id
        WHERE c.gstin = %s
    """

    try:
        db_conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')   
        )
        with db_conn.cursor() as cursor:
            cursor.execute(query, (gstin,))  # Pass parameters as a tuple
            results = cursor.fetchall()
            print(results)
            return results  # Returns a list of tuples

    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return []
     
    finally:
        db_conn.close()

def getAllDataFromSQL(gst: str):
    # SQL query to fetch all data from the database

    query = f"""SELECT c.name,c.trade_name,c.phone_number, ds.documents_submitted, ds.year , ds.month ,lf.fixed_rate,lf.late_fee
        FROM masterClientTable c
        JOIN documents_submission ds ON c.client_id = ds.client_id JOIN late_fee lf on c.client_id = lf.client_id
        WHERE c.gstin = '{gst}'"""  

    try:
        # db_conn = psycopg2.connect(
        #     host=os.getenv('DB_HOST'),
        #     port=os.getenv('DB_PORT'),
        #     database=os.getenv('DB_NAME'),
        #     user=os.getenv('DB_USER'),
        #     password=os.getenv('DB_PASSWORD')   
        # )
        with db_conn.cursor() as cursor:
            cursor.execute(query)  # Pass parameters as a tuple
            results = cursor.fetchall()
            print(results)
            return results  # Returns a list of tuples

    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return []
    

def updateLateFeeDataToSQL(gst: str, lateFee: int):
    # SQL query to fetch all data from the database

    print("---------------->",gst,lateFee)

    query = f"""
        UPDATE late_fee lf
            SET late_fee = {lateFee} ,
            updated_date = now()
            FROM masterClientTable c
            WHERE lf.client_id = c.client_id
            AND c.gstin = '{gst}'
            AND lf.client_id = c.client_id;
    """

    try:
        # db_conn = psycopg2.connect(
        #     host=os.getenv('DB_HOST'),
        #     port=os.getenv('DB_PORT'),
        #     database=os.getenv('DB_NAME'),
        #     user=os.getenv('DB_USER'),
        #     password=os.getenv('DB_PASSWORD')   
        # )
        with db_conn.cursor() as cursor:
            cursor.execute(query)  # Pass parameters as a tuple
            db_conn.commit()
            print("Updated")      
            return []      

    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return []
    

    
     
    # finally:
    #     db_conn.close()            



# def get_clients_reminders():
#     """Fetch all client reminders from the database."""
#     try:
#         cursor = db_conn.cursor()
#         cursor.execute("""
#             SELECT c.phone_number, c.name, r.reminder_date, r.reminder_message
#             FROM clients c
#             JOIN reminders r ON c.id = r.client_id
#             WHERE r.reminder_date >= CURRENT_DATE
#             ORDER BY r.reminder_date
#         """)
#         reminders = cursor.fetchall()
#         cursor.close()
        
#         return reminders
#     except Exception as e:
#         logging.error(f"Error fetching reminders: {str(e)}")
#         return []

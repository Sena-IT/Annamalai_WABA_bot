import os
import psycopg2
import logging
from datetime import datetime
from dotenv import load_dotenv, find_dotenv

# Load Environment Variables
dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

# Database Connection
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
def insert_client(data):
    """
    Insert client data into the clients table.
    """
    query = """
        INSERT INTO clients (name, aadhar_number, phone_number, authorized_phone_numbers, 
        aadhar_verified, phone_number_verified, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
    """
    values = (
        data.get('name'),
        data.get('aadhar_number'),
        data.get('phone_number'),
        json.dumps(data.get('authorized_phone_numbers')),
        data.get('aadhar_verified'),
        data.get('phone_number_verified')
    )
    
    with db_conn.cursor() as cursor:
        cursor.execute(query, values)
        db_conn.commit()
        logging.info("✅ Client inserted successfully.")


def get_client_by_phone(phone_number):
    """
    Fetch client details by phone number.
    """
    query = """
        SELECT client_id, name, aadhar_number, phone_number, authorized_phone_numbers
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
                "authorized_phone_numbers": result[4]
            }
        return None


# ===========================
# ✅ SRN Operations
# ===========================
def insert_srn(data):
    """
    Insert SRN data into srns table.
    """
    query = """
        INSERT INTO srns (client_id, service_id, due_date, task_type, status, 
        payment_status, service_specific_data, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
    """
    values = (
        data.get('client_id'),
        data.get('service_id'),
        data.get('due_date'),
        data.get('task_type'),
        data.get('status'),
        data.get('payment_status'),
        json.dumps(data.get('service_specific_data'))
    )
    
    with db_conn.cursor() as cursor:
        cursor.execute(query, values)
        db_conn.commit()
        logging.info("✅ SRN inserted successfully.")


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

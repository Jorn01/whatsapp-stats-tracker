import sqlite3
import re
from datetime import datetime

def parse_whatsapp_chat(input_file, db_file):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Updated schema to include 'is_poll'
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            sender TEXT,
            message_content TEXT,
            has_media INTEGER,
            is_poll INTEGER
        )
    ''')

    # Regex to identify the start of a new message
    # Format: MM/DD/YY, HH:MM - Sender: Message
    log_pattern = re.compile(r'^(\d{1,2}/\d{1,2}/\d{2}, \d{2}:\d{2}) - (.*)$')

    current_entry = None
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                stripped_line = line.rstrip()
                
                if not stripped_line:
                    continue

                match = log_pattern.match(stripped_line)

                if match:
                    # Save previous entry before starting new one
                    if current_entry:
                        finalize_and_save(cursor, current_entry)

                    # Start new entry
                    raw_timestamp, content_body = match.groups()
                    
                    # Date Parsing
                    try:
                        dt_obj = datetime.strptime(raw_timestamp, '%m/%d/%y, %H:%M')
                        formatted_timestamp = dt_obj.strftime('%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        formatted_timestamp = raw_timestamp

                    # Sender Parsing
                    if ': ' in content_body:
                        sender, message = content_body.split(': ', 1)
                    else:
                        sender = 'System'
                        message = content_body

                    current_entry = {
                        'timestamp': formatted_timestamp,
                        'sender': sender,
                        'message_content': message,
                        'has_media': 0,
                        'is_poll': 0
                    }

                    # Initial check for flags in the first line
                    if "<Media omitted>" in message:
                        current_entry['has_media'] = 1
                    if "POLL:" in message:
                        current_entry['is_poll'] = 1

                else:
                    # Handle Multi-line (Poll options or long text)
                    if current_entry:
                        current_entry['message_content'] += '\n' + stripped_line
                        
                        # Check flags in continuation lines
                        if "<Media omitted>" in stripped_line:
                            current_entry['has_media'] = 1
                        # WhatsApp exports often put "POLL:" on the first line, 
                        # but we check here just in case formatting varies.
                        if "POLL:" in stripped_line:
                            current_entry['is_poll'] = 1
                        if stripped_line.strip().startswith("OPTION:"):
                            current_entry['is_poll'] = 1

            # Save the last entry
            if current_entry:
                finalize_and_save(cursor, current_entry)

        conn.commit()
        print("Database created successfully")

    except FileNotFoundError:
        print(f"Error: The file '{input_file}' was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()

def finalize_and_save(cursor, entry):
    """
    Helper function to save the entry to DB.
    """
    cursor.execute('''
        INSERT INTO messages (timestamp, sender, message_content, has_media, is_poll)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        entry['timestamp'], 
        entry['sender'], 
        entry['message_content'], 
        entry['has_media'], 
        entry['is_poll']
    ))

if __name__ == "__main__":
    parse_whatsapp_chat('chat.txt', 'chat_data.db')
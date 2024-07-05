import os
import shutil
import vobject
import requests
import json
import argparse
from openai import OpenAI
from dotenv import load_dotenv
from typing import Dict, List, Optional, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich import box
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
import base64

# For cross-platform single-character input
import sys
if sys.platform == 'win32':
    import msvcrt
else:
    import tty
    import termios

# Load environment variables
load_dotenv()

# Configuration
# CONFIG = {
#     "SERPER_API_KEY": os.getenv("SERPER_API_KEY"),
#     "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY"),
#     "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
#     "SYSTEM_PROMPT": os.getenv("SYSTEM_PROMPT", "You are a helpful assistant that summarizes information about people."),
#     "USER_PROMPT": os.getenv("USER_PROMPT", "Please summarize the following information about a person in 2-3 sentences:"),
#     "OPENAI_MODEL": os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
#     "STATE_FILE": 'contact_sort_state.json',
#     "GMAIL_TOKEN_FILE": 'token.pickle',
#     "GMAIL_CREDENTIALS_FILE": 'credentials.json',
# }

import os
import yaml
from dotenv import load_dotenv
from typing import Dict, Any

def load_config(config_path: str = 'vcard_curator_config.yaml') -> Dict[str, Any]:
    # Load environment variables
    load_dotenv()

    # Load YAML configuration
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)

    # Add API keys from environment variables
    config['serper_api_key'] = os.getenv('SERPER_API_KEY')
    config['tavily_api_key'] = os.getenv('TAVILY_API_KEY')
    config['openai_api_key'] = os.getenv('OPENAI_API_KEY')

    return config

# Load configuration
CONFIG = load_config()

# Validate configuration
required_keys = ['serper_api_key', 'tavily_api_key', 'openai_api_key']
for key in required_keys:
    if not CONFIG.get(key):
        raise ValueError(f"Missing required configuration: {key}. Please check your .env file.")

# Initialize OpenAI client
client = OpenAI(api_key=CONFIG["openai_api_key"])

# Initialize Rich console
console = Console()

def getch():
    if sys.platform == 'win32':
        return msvcrt.getch().decode('utf-8').lower()
    else:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1).lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

class GmailService:
    def __init__(self):
        self.service = self.get_gmail_service()

    def get_gmail_service(self):
        creds = None
        if os.path.exists(CONFIG['gmail_token_file']):
            with open(CONFIG['gmail_token_file'], 'rb') as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CONFIG['gmail_credentials_file'], ['https://www.googleapis.com/auth/gmail.readonly'])
                creds = flow.run_local_server(port=0)
            with open(CONFIG['gmail_token_file'], 'wb') as token:
                pickle.dump(creds, token)
        return build('gmail', 'v1', credentials=creds)

    def get_email_interaction_count(self, email: str) -> int:
        query = f'from:{email} OR to:{email}'
        try:
            results = self.service.users().messages().list(userId='me', q=query).execute()
            return int(results.get('resultSizeEstimate', 0))
        except Exception as e:
            console.print(f"Error fetching email count for {email}: {str(e)}", style="bold red")
            return 0

    def get_last_email_subjects(self, email: str) -> List[str]:
        query = f'from:{email} OR to:{email}'
        subjects = []
        try:
            results = self.service.users().messages().list(userId='me', q=query, maxResults=CONFIG['email_subject_count']).execute()
            if 'messages' in results:
                for message_data in results['messages']:
                    message = self.service.users().messages().get(userId='me', id=message_data['id']).execute()
                    headers = message['payload']['headers']
                    subject_header = next((header for header in headers if header['name'].lower() == 'subject'), None)
                    if subject_header:
                        subjects.append(subject_header['value'])
        except Exception as e:
            console.print(f"Error fetching email subjects for {email}: {str(e)}", style="bold red")
        return subjects

    def get_email_interaction_data(self, email: str) -> Tuple[int, List[str]]:
        count = self.get_email_interaction_count(email)
        subjects = self.get_last_email_subjects(email)
        return count, subjects

    def get_last_interaction_date(self, email: str) -> Optional[str]:
        query = f'from:{email} OR to:{email}'
        try:
            results = self.service.users().messages().list(userId='me', q=query, maxResults=1).execute()
            if 'messages' in results and results['messages']:
                message = self.service.users().messages().get(userId='me', id=results['messages'][0]['id']).execute()
                return message['internalDate']
        except Exception as e:
            console.print(f"Error fetching last interaction date for {email}: {str(e)}", style="bold red")
        return None

class SearchService:
    @staticmethod
    def search_serper(query: str) -> Dict:
        url = "https://google.serper.dev/search"
        payload = json.dumps({"q": query})
        headers = {
            'X-API-KEY': CONFIG["serper_api_key"],
            'Content-Type': 'application/json'
        }
        response = requests.post(url, headers=headers, data=payload)
        return response.json()

    @staticmethod
    def search_tavily(query: str) -> Dict:
        url = "https://api.tavily.com/search"
        params = {
            "api_key": CONFIG["tavily_api_key"],
            "query": query,
            "search_depth": "basic",
            "include_images": False,
            "max_results": CONFIG["tavily_max_results"]
        }
        response = requests.get(url, params=params)
        return response.json()

    @classmethod
    def combined_search(cls, name: str, email: Optional[str] = None) -> List[Dict]:
        query = f"{name} {email}" if email else name
        serper_results = cls.search_serper(query)
        tavily_results = cls.search_tavily(f"who is {query}")

        combined_results = []

        # Process Serper results
        if 'organic' in serper_results:
            for result in serper_results['organic'][:3]:
                combined_results.append({
                    'title': result['title'],
                    'snippet': result['snippet'],
                    'source': 'Serper'
                })

        # Process Tavily results
        if 'results' in tavily_results:
            for result in tavily_results['results'][:3]:
                combined_results.append({
                    'title': result['title'],
                    'snippet': result['description'],
                    'source': 'Tavily'
                })

        return combined_results

class ContactManager:
    def __init__(self, main_dir: str, secondary_dir: str):
        self.main_dir = main_dir
        self.secondary_dir = secondary_dir
        self.state = self.load_state()
        self.gmail_service = GmailService()

    def load_state(self) -> Dict:
        default_state = {'processed_files': [], 'skipped_files': []}
        if os.path.exists(CONFIG["state_file"]):
            with open(CONFIG["state_file"], 'r') as f:
                loaded_state = json.load(f)
                # Ensure both keys exist in the loaded state
                for key in default_state:
                    if key not in loaded_state:
                        loaded_state[key] = default_state[key]
                return loaded_state
        return default_state

    def save_state(self):
        with open(CONFIG["state_file"], 'w') as f:
            json.dump(self.state, f)

    def summarize_results(self, results: List[Dict], email_count: int, email_subjects: List[str]) -> str:
        if not results:
            return "No relevant information found."

        text_to_summarize = "Information about the person:\n\n"
        for result in results:
            text_to_summarize += f"Title: {result['title']}\n"
            text_to_summarize += f"Snippet: {result['snippet']}\n"
            text_to_summarize += f"Source: {result['source']}\n\n"

        text_to_summarize += f"Email Interaction Data:\n"
        text_to_summarize += f"Total number of email interactions: {email_count}\n"
        if email_subjects:
            text_to_summarize += f"Last {CONFIG['email_subject_count']} email subjects:\n"
            for subject in email_subjects:
                text_to_summarize += f"- {subject}\n"

        try:
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": CONFIG["system_prompt"]},
                    {"role": "user", "content": f"{CONFIG['user_prompt']}\n\n{text_to_summarize}"}
                ],
                model=CONFIG["openai_model"],
            )
            summary = chat_completion.choices[0].message.content.strip()
        except Exception as e:
            console.print(f"Error generating summary: {str(e)}", style="bold red")
            summary = "Unable to generate summary due to an error."

        return summary

    def create_contact_panel(self, vcard: vobject.vCard, email_count: int, email_subjects: List[str]) -> Panel:
        contact_table = Table(show_header=False, expand=True, box=box.SIMPLE)
        contact_table.add_column("Field", style="cyan")
        contact_table.add_column("Value", style="green")

        contact_table.add_row("Name", vcard.fn.value)
        if hasattr(vcard, 'tel'):
            contact_table.add_row("Phone", vcard.tel.value)
        if hasattr(vcard, 'email'):
            contact_table.add_row("Email", vcard.email.value)
        if hasattr(vcard, 'org'):
            contact_table.add_row("Organization", vcard.org.value[0])
        contact_table.add_row("Email Interactions", str(email_count) if email_count > 0 else "No interactions")
        if email_subjects:
            contact_table.add_row("Last Email Subject", email_subjects[0])

        return Panel(contact_table, title="Contact Information", border_style="blue")

    def create_summary_panel(self, summary: str) -> Panel:
        return Panel(summary, title="Summary", border_style="green")

    def display_contact_info(self, vcard: vobject.vCard, summary: str, email_count: int, email_subjects: List[str]):
        layout = Layout()
        layout.split_column(
            Layout(Panel("Contact Sorter", style="bold magenta"), size=3),
            Layout(name="main"),
            Layout(Panel("Keep (K), Move (M), Skip (S), or Quit (Q)?", style="bold yellow"), size=3)
        )
        layout["main"].split_row(
            self.create_contact_panel(vcard, email_count, email_subjects),
            self.create_summary_panel(summary)
        )
        console.print(layout)

    def process_contact(self, filename: str, file_path: str):
        with open(file_path, 'r') as f:
            vcard = vobject.readOne(f.read())

        email = vcard.email.value if hasattr(vcard, 'email') else None
        email_count, email_subjects = self.gmail_service.get_email_interaction_data(email) if email else (0, [])
        search_results = SearchService.combined_search(vcard.fn.value, email)
        summary = self.summarize_results(search_results, email_count, email_subjects)

        console.clear()
        self.display_contact_info(vcard, summary, email_count, email_subjects)

        while True:
            choice = getch().lower()
            if choice in ['k', 'm', 's', 'q']:
                break
            console.print("Invalid choice. Please press K, M, S, or Q.", style="bold red")

        if choice == 'q':
            return False
        elif choice == 'm':
            shutil.move(file_path, os.path.join(self.secondary_dir, filename))
            console.print(f"Moved {filename} to secondary folder.", style="bold green")
            self.state['processed_files'].append(filename)
        elif choice == 's':
            console.print(f"Skipped {filename}.", style="bold yellow")
            self.state['skipped_files'].append(filename)
        else:
            console.print(f"Kept {filename} in main folder.", style="bold blue")
            self.state['processed_files'].append(filename)

        self.save_state()
        return True

    def sort_contacts(self):
        processed_files = set(self.state['processed_files'])
        skipped_files = set(self.state['skipped_files'])

        for filename in os.listdir(self.main_dir):
            if filename.endswith('.vcf') and filename not in processed_files and filename not in skipped_files:
                file_path = os.path.join(self.main_dir, filename)
                if not self.process_contact(filename, file_path):
                    console.print("Quitting the sorting process.", style="bold red")
                    return

        console.print("All contacts have been processed.", style="bold green")

def parse_arguments():
    parser = argparse.ArgumentParser(description="Sort contacts between main and secondary directories.")
    parser.add_argument("main_dir", help="Path to the main contacts directory")
    parser.add_argument("secondary_dir", help="Path to the secondary contacts directory")
    return parser.parse_args()

def main():
    args = parse_arguments()

    if not os.path.exists(args.main_dir):
        raise ValueError(f"Main directory does not exist: {args.main_dir}")

    if not os.path.exists(args.secondary_dir):
        os.makedirs(args.secondary_dir)
        console.print(f"Created secondary directory: {args.secondary_dir}", style="bold green")

    contact_manager = ContactManager(args.main_dir, args.secondary_dir)
    contact_manager.sort_contacts()
    console.print("Sorting completed.", style="bold green")

if __name__ == "__main__":
    main()

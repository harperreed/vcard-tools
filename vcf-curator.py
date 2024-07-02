import os
import shutil
import vobject
import requests
import json
import argparse
from openai import OpenAI
from dotenv import load_dotenv
from typing import Dict, List, Optional

# Load environment variables
load_dotenv()

# Configuration
CONFIG = {
    "SERPER_API_KEY": os.getenv("SERPER_API_KEY"),
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "SYSTEM_PROMPT": os.getenv("SYSTEM_PROMPT", "You are a helpful assistant that summarizes information about people."),
    "USER_PROMPT": os.getenv("USER_PROMPT", "Please summarize the following information about a person in 2-3 sentences:"),
    "OPENAI_MODEL": os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
    "STATE_FILE": 'contact_sort_state.json',
}

# Validate configuration
if not CONFIG["SERPER_API_KEY"] or not CONFIG["OPENAI_API_KEY"]:
    raise ValueError("Missing API keys. Please check your .env file.")

# Initialize OpenAI client
client = OpenAI(api_key=CONFIG["OPENAI_API_KEY"])

class ContactManager:
    def __init__(self, main_dir: str, secondary_dir: str):
        self.main_dir = main_dir
        self.secondary_dir = secondary_dir
        self.state = self.load_state()

    def load_state(self) -> Dict:
        if os.path.exists(CONFIG["STATE_FILE"]):
            with open(CONFIG["STATE_FILE"], 'r') as f:
                return json.load(f)
        return {'processed_files': []}

    def save_state(self):
        with open(CONFIG["STATE_FILE"], 'w') as f:
            json.dump(self.state, f)

    def search_person(self, name: str, email: Optional[str] = None) -> Dict:
        query = f"{name} {email}" if email else name
        url = "https://google.serper.dev/search"
        payload = json.dumps({"q": query})
        headers = {
            'X-API-KEY': CONFIG["SERPER_API_KEY"],
            'Content-Type': 'application/json'
        }
        response = requests.post(url, headers=headers, data=payload)
        return response.json()

    def summarize_results(self, results: Dict) -> str:
        if 'organic' not in results or not results['organic']:
            return "No relevant information found."

        text_to_summarize = "Information about the person:\n\n"
        for result in results['organic'][:3]:
            text_to_summarize += f"Title: {result['title']}\n"
            text_to_summarize += f"Snippet: {result['snippet']}\n\n"

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": CONFIG["SYSTEM_PROMPT"]},
                {"role": "user", "content": f"{CONFIG['USER_PROMPT']}\n\n{text_to_summarize}"}
            ],
            model=CONFIG["OPENAI_MODEL"],
        )

        return chat_completion.choices[0].message.content.strip()

    @staticmethod
    def display_contact(vcard: vobject.vCard):
        print("\nContact Details:")
        print(f"Name: {vcard.fn.value}")
        if hasattr(vcard, 'tel'):
            print(f"Phone: {vcard.tel.value}")
        if hasattr(vcard, 'email'):
            print(f"Email: {vcard.email.value}")

    def process_contact(self, filename: str, file_path: str):
        with open(file_path, 'r') as f:
            vcard = vobject.readOne(f.read())

        self.display_contact(vcard)

        email = vcard.email.value if hasattr(vcard, 'email') else None
        search_results = self.search_person(vcard.fn.value, email)
        summary = self.summarize_results(search_results)
        print("\nSummary of search results:")
        print(summary)

        choice = input("\nKeep (K), Move (M), or Quit (Q)? ").strip().upper()
        while choice not in ['K', 'M', 'Q']:
            choice = input("Invalid choice. Keep (K), Move (M), or Quit (Q)? ").strip().upper()

        if choice == 'Q':
            return False
        elif choice == 'M':
            shutil.move(file_path, os.path.join(self.secondary_dir, filename))
            print(f"Moved {filename} to secondary folder.")
        else:
            print(f"Kept {filename} in main folder.")

        self.state['processed_files'].append(filename)
        self.save_state()
        return True

    def sort_contacts(self):
        processed_files = set(self.state['processed_files'])

        for filename in os.listdir(self.main_dir):
            if filename.endswith('.vcf') and filename not in processed_files:
                file_path = os.path.join(self.main_dir, filename)
                if not self.process_contact(filename, file_path):
                    print("Quitting the sorting process.")
                    return

        print("All contacts have been processed.")

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
        print(f"Created secondary directory: {args.secondary_dir}")

    contact_manager = ContactManager(args.main_dir, args.secondary_dir)
    contact_manager.sort_contacts()
    print("Sorting completed.")

if __name__ == "__main__":
    main()

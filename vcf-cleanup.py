import os
import vobject
import yaml
import re
import logging
import hashlib
import shutil
from typing import Dict, List, Tuple, Any, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VCard:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.content: Optional[str] = None
        self.vobject: Optional[vobject.base.Component] = None
        self.is_valid = False
        self.load()

    def load(self):
        try:
            with open(self.filepath, 'r') as f:
                self.content = f.read()
            if self.content.strip():
                self.vobject = vobject.readOne(self.content)
                self.is_valid = True
        except Exception as e:
            logger.error(f"Error loading {self.filename}: {str(e)}")

    def has_attribute(self, attr: str) -> bool:
        return self.is_valid and hasattr(self.vobject, attr)

    def get_attribute(self, attr: str) -> Any:
        return getattr(self.vobject, attr) if self.has_attribute(attr) else None

class VCardCleaner:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.keywords = config['keywords']
        self.auto_delete = config.get('auto_delete', False)
        self.base_trash_dir = config['trash_directory']
        self.patterns = {
            'email': re.compile(r'\b([A-Za-z0-9._%+-]+)@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', re.IGNORECASE),
            'phone': re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
            'name': re.compile(r'\bFN:(.+)\b'),
            'org': re.compile(r'\bORG:(.+)\b')
        }

    def get_trash_dir(self, source_dir: str) -> str:
        dir_hash = hashlib.md5(source_dir.encode()).hexdigest()
        trash_dir = os.path.join(self.base_trash_dir, dir_hash)
        os.makedirs(trash_dir, exist_ok=True)
        logger.debug(f"Created trash directory: {trash_dir}")
        return trash_dir

    def move_to_trash(self, vcard: VCard, trash_dir: str) -> None:
        trash_path = os.path.join(trash_dir, vcard.filename)
        shutil.move(vcard.filepath, trash_path)
        logger.info(f"Moved {vcard.filename} to trash: {trash_path}")

    def is_empty_card(self, vcard: VCard) -> bool:
        has_name_or_org = vcard.has_attribute('n') or vcard.has_attribute('org')
        has_contact = vcard.has_attribute('email') or vcard.has_attribute('tel')
        empty = not (has_name_or_org and has_contact)
        logger.debug(f"Card empty check: {empty} (Has name/org: {has_name_or_org}, Has contact: {has_contact})")
        return empty

    def is_valid_card(self, vcard: VCard) -> bool:
        valid = vcard.has_attribute('fn') or (vcard.has_attribute('org') and (vcard.has_attribute('email') or vcard.has_attribute('tel')))
        logger.debug(f"Card validity check: {valid}")
        return valid

    def contains_keywords(self, vcard: VCard) -> bool:
        if not vcard.content:
            return False
        return self.keyword_match(vcard.content)

    def keyword_match(self, content: str) -> bool:
        email_matches = self.patterns['email'].finditer(content)
        for email_match in email_matches:
            local_part = email_match.group(1).lower()
            if any(keyword.lower() in local_part for keyword in self.keywords):
                return True
        return any(keyword.lower() in content.lower() for keyword in self.keywords)

    def text_search_vcard(self, content: str) -> Tuple[bool, bool]:
        has_email = bool(self.patterns['email'].search(content))
        has_phone = bool(self.patterns['phone'].search(content))
        has_name = bool(self.patterns['name'].search(content))
        has_org = bool(self.patterns['org'].search(content))
        logger.debug(f"Text search results - Email: {has_email}, Phone: {has_phone}, Name: {has_name}, Org: {has_org}")
        return (has_name or has_org), (has_email or has_phone)

    def process_vcard(self, vcard: VCard, trash_dir: str) -> Dict[str, int]:
        counters = {
            'zero_byte_moved': 0,
            'empty_content_skipped': 0,
            'parse_error_processed': 0,
            'empty_card_moved': 0,
            'keyword_match_moved': 0,
            'user_kept': 0
        }

        logger.info(f"Processing file: {vcard.filename}")

        if os.path.getsize(vcard.filepath) == 0:
            self.move_to_trash(vcard, trash_dir)
            logger.info(f"Moved zero-byte file to trash: {vcard.filename}")
            counters['zero_byte_moved'] += 1
            return counters

        if not vcard.content:
            logger.info(f"File is empty (but not zero bytes): {vcard.filename}")
            counters['empty_content_skipped'] += 1
            return counters

        should_move, move_reason = self.determine_move_action(vcard)

        if should_move:
            logger.info(f"Card {vcard.filename} is {move_reason}.")
            logger.debug("Card content to be moved:")
            logger.debug(vcard.content)
            if self.auto_delete or self.user_confirms_move(vcard.filename):
                self.move_to_trash(vcard, trash_dir)
                logger.info(f"Moved to trash: {vcard.filename}")
                counters['empty_card_moved' if "empty" in move_reason else 'keyword_match_moved'] += 1
            else:
                logger.info(f"Kept {vcard.filename}")
                counters['user_kept'] += 1
        else:
            logger.info(f"Kept {vcard.filename} (not empty and no keyword match)")

        return counters

    def determine_move_action(self, vcard: VCard) -> Tuple[bool, str]:
        if vcard.is_valid:
            if not self.is_valid_card(vcard):
                logger.info(f"Invalid card {vcard.filename} (missing FN/ORG or contact info). Falling back to text search.")
                return self.text_search_move_action(vcard.content)

            should_move = self.is_empty_card(vcard)
            move_reason = "empty (no name/org AND no email/phone)" if should_move else ""

            if not should_move and self.contains_keywords(vcard):
                should_move = True
                move_reason = "contains one or more keywords"
        else:
            logger.info(f"Parsing failed for {vcard.filename}. Falling back to text search.")
            return self.text_search_move_action(vcard.content)

        return should_move, move_reason

    def text_search_move_action(self, content: str) -> Tuple[bool, str]:
        has_name_or_org, has_contact = self.text_search_vcard(content)
        should_move = not (has_name_or_org and has_contact)
        move_reason = "empty (no name/org AND no email/phone) based on text search" if should_move else ""

        if not should_move and self.keyword_match(content):
            should_move = True
            move_reason = "contains one or more keywords based on text search"

        return should_move, move_reason

    def user_confirms_move(self, filename: str) -> bool:
        return input(f"Move {filename} to trash? (y/n): ").lower() == 'y'

    def cleanup_vcards(self, directory: str) -> None:
        trash_dir = self.get_trash_dir(directory)
        counters = {
            'total_files': 0,
            'zero_byte_moved': 0,
            'empty_content_skipped': 0,
            'parse_error_processed': 0,
            'empty_card_moved': 0,
            'keyword_match_moved': 0,
            'user_kept': 0
        }

        for filename in os.listdir(directory):
            if filename.endswith('.vcf'):
                counters['total_files'] += 1
                filepath = os.path.join(directory, filename)
                try:
                    vcard = VCard(filepath)
                    result = self.process_vcard(vcard, trash_dir)
                    for key, value in result.items():
                        counters[key] += value
                except Exception as e:
                    logger.error(f"An error occurred while processing {filename}: {str(e)}")

        self.print_summary(counters, trash_dir)

    def print_summary(self, counters: Dict[str, int], trash_dir: str) -> None:
        summary = f"""
        Cleanup Summary:
        Total .vcf files processed: {counters['total_files']}
        Zero-byte files moved to trash: {counters['zero_byte_moved']}
        Empty content files skipped: {counters['empty_content_skipped']}
        Files processed with text search due to parse errors: {counters['parse_error_processed']}
        Empty cards moved to trash: {counters['empty_card_moved']}
        Keyword match cards moved to trash: {counters['keyword_match_moved']}
        Cards kept after user review: {counters['user_kept']}
        Total cards moved to trash: {counters['zero_byte_moved'] + counters['empty_card_moved'] + counters['keyword_match_moved']}
        Trash directory: {trash_dir}
        """
        print(summary)
        logger.info(summary)

def load_config(config_path: str) -> Dict[str, Any]:
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'vcard_cleanup_config.yaml')
    config = load_config(config_path)

    print("Current keywords:", config['keywords'])
    print("Trash directory:", config['trash_directory'])

    directory = input("Enter the directory path containing vCards: ")
    while not os.path.isdir(directory):
        print("Invalid directory path. Please try again.")
        directory = input("Enter the directory path containing vCards: ")

    cleaner = VCardCleaner(config)
    cleaner.cleanup_vcards(directory)

if __name__ == "__main__":
    main()

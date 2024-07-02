#!/usr/bin/env python3

import os
import vobject
import logging
from collections import defaultdict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import yaml
import shutil
import hashlib
from typing import Dict, List, Tuple, Optional
import sys
import re
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set up file logging for AI decisions
ai_logger = logging.getLogger('ai_decisions')
ai_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler('ai_decisions.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
ai_logger.addHandler(file_handler)

# Initialize OpenAI client
client = OpenAI()  # This will automatically use the OPENAI_API_KEY from the environment

class Config:
    def __init__(self, config_path: str = 'vcard_dupechecker_config.yaml'):
        self.default_config = {
            'similarity_threshold': 0.8,
            'ai_decision_threshold': 0.8,
            'keep_originals': False,
            'merged_dir': 'merged_vcards',
            'openai_model': 'gpt-3.5-turbo'
        }
        self.config = self.load_config(config_path)

    def load_config(self, config_path: str) -> Dict:
        try:
            with open(config_path, 'r') as file:
                user_config = yaml.safe_load(file)
            logger.info(f"Loaded configuration from {config_path}")
            return {**self.default_config, **user_config}
        except FileNotFoundError:
            logger.warning(f"Config file {config_path} not found. Using default settings.")
            return self.default_config

    def __getitem__(self, key):
        return self.config[key]

class VCardHandler:
    @staticmethod
    def read_vcard(file_path: str) -> Optional[vobject.vCard]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return vobject.readOne(f.read())
        except Exception as e:
            logger.error(f"Error reading {file_path}: {str(e)}")
            return None

    @staticmethod
    def extract_key_info(vcard: vobject.vCard) -> Tuple[str, str, str]:
        name = str(vcard.fn.value) if hasattr(vcard, 'fn') else ''
        email = str(vcard.email.value) if hasattr(vcard, 'email') else ''
        tel = str(vcard.tel.value) if hasattr(vcard, 'tel') else ''

        if not name and email:
            name = VCardHandler.guess_name_from_email(email)

        logger.debug(f"Extracted info - Name: {name}, Email: {email}, Tel: {tel}")
        return name, email, tel

    @staticmethod
    def guess_name_from_email(email: str) -> str:
        local_part = email.split('@')[0]
        name_parts = re.split(r'[._-]', local_part)
        return ' '.join(part.capitalize() for part in name_parts)

    @staticmethod
    def merge_vcards(vcard1: vobject.vCard, vcard2: vobject.vCard, merge_instructions: Optional[Dict] = None) -> Optional[vobject.vCard]:
        try:
            merged = vobject.vCard()

            def copy_prop(prop):
                if merge_instructions and prop in merge_instructions:
                    if merge_instructions[prop] == 'vcard1':
                        if hasattr(vcard1, prop):
                            setattr(merged, prop, getattr(vcard1, prop))
                    elif merge_instructions[prop] == 'vcard2':
                        if hasattr(vcard2, prop):
                            setattr(merged, prop, getattr(vcard2, prop))
                    else:  # Default behavior if not specified
                        if hasattr(vcard1, prop):
                            setattr(merged, prop, getattr(vcard1, prop))
                        elif hasattr(vcard2, prop):
                            setattr(merged, prop, getattr(vcard2, prop))
                else:
                    if hasattr(vcard1, prop):
                        setattr(merged, prop, getattr(vcard1, prop))
                    elif hasattr(vcard2, prop):
                        setattr(merged, prop, getattr(vcard2, prop))

            for prop in ['fn', 'n', 'email', 'tel', 'adr', 'org', 'title', 'note']:
                copy_prop(prop)

            for prop in ['email', 'tel', 'adr']:
                values = set()
                if hasattr(vcard1, prop):
                    values.update([str(v.value) for v in getattr(vcard1, prop.lower() + '_list')])
                if hasattr(vcard2, prop):
                    values.update([str(v.value) for v in getattr(vcard2, prop.lower() + '_list')])
                for value in values:
                    merged.add(prop).value = value

            if not hasattr(merged, 'fn'):
                name, email, _ = VCardHandler.extract_key_info(merged)
                merged.add('fn')
                merged.fn.value = name if name else email

            logger.debug(f"Merged vCard created with FN: {merged.fn.value}")
            return merged
        except Exception as e:
            logger.error(f"Error in merge_vcards: {str(e)}")
            return None

    @staticmethod
    def serialize_vcard(vcard: vobject.vCard) -> Optional[str]:
        try:
            return vcard.serialize()
        except Exception as e:
            logger.error(f"Error during vCard serialization: {str(e)}")
            logger.info("Attempting to create a basic vCard string as fallback")
            try:
                return VCardHandler.create_basic_vcard_string(vcard)
            except Exception as e:
                logger.error(f"Fallback serialization also failed: {str(e)}")
                return None

    @staticmethod
    def create_basic_vcard_string(vcard: vobject.vCard) -> str:
        lines = ["BEGIN:VCARD", "VERSION:3.0"]

        for attr in ['fn', 'n', 'email', 'tel', 'adr', 'org', 'title', 'note']:
            if hasattr(vcard, attr):
                value = getattr(vcard, attr)
                if attr == 'n':
                    if isinstance(value.value, list):
                        value_str = ';'.join(str(v) for v in value.value)
                    else:
                        value_str = str(value.value)
                    lines.append(f"N:{value_str}")
                elif attr in ['email', 'tel', 'adr']:
                    for item in getattr(vcard, attr + '_list'):
                        lines.append(f"{attr.upper()}:{item.value}")
                else:
                    lines.append(f"{attr.upper()}:{value.value}")

        lines.append("END:VCARD")
        return "\n".join(lines)

    @staticmethod
    def debug_vcard(vcard: vobject.vCard) -> str:
        debug_info = []
        for attr in dir(vcard):
            if not attr.startswith('__') and not callable(getattr(vcard, attr)):
                value = getattr(vcard, attr)
                debug_info.append(f"{attr}: {type(value)} = {value}")
        return "\n".join(debug_info)

class AIAssistant:
    def __init__(self, config: Config):
        self.config = config

    def get_merge_decision(self, vcard1: vobject.vCard, vcard2: vobject.vCard, similarity: float) -> Tuple[bool, Optional[Dict], str]:
        vcard1_info = self.format_vcard_info(vcard1)
        vcard2_info = self.format_vcard_info(vcard2)

        prompt = f"""
        You are an AI assistant helping to merge vCard contacts. You will be given information about two vCards that might be duplicates. Your task is to decide whether they should be merged and if so, how to merge them.

        vCard 1:
        {vcard1_info}

        vCard 2:
        {vcard2_info}

        Similarity score: {similarity}

        Please provide your decision in the following format:
        1. Should these vCards be merged? (Yes/No)
        2. If yes, provide merge instructions for each field (fn, n, email, tel, adr, org, title, note) in the format:
           field: vcard1 or vcard2 (choose the one that seems more complete or accurate)

        Explain your reasoning for the merge decision and field choices.
        """

        try:
            response = client.chat.completions.create(
                model=self.config['openai_model'],
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that makes decisions about merging vCard contacts."},
                    {"role": "user", "content": prompt}
                ]
            )

            ai_response = response.choices[0].message.content.strip()
            ai_logger.info(f"AI Response for similarity {similarity}:\n{ai_response}")

            # Parse the AI response
            lines = ai_response.split('\n')
            should_merge = lines[0].lower().startswith("1. yes")

            merge_instructions = {}
            if should_merge:
                for line in lines[1:]:
                    if ':' in line:
                        field, choice = line.split(':')
                        field = field.strip().lower()
                        choice = choice.strip().lower()
                        if choice in ['vcard1', 'vcard2']:
                            merge_instructions[field] = choice

            return should_merge, merge_instructions, ai_response

        except Exception as e:
            logger.error(f"Error getting AI merge decision: {str(e)}")
            return False, None, str(e)

    def format_vcard_info(self, vcard: vobject.vCard) -> str:
        info = []
        for field in ['fn', 'n', 'email', 'tel', 'adr', 'org', 'title', 'note']:
            if hasattr(vcard, field):
                value = getattr(vcard, field).value
                info.append(f"{field.upper()}: {value}")
        return "\n".join(info)

class DuplicateFinder:
    def __init__(self, config: Config):
        self.config = config

    def find_duplicates_ml(self, directory: str) -> Dict[str, List[Tuple[str, float]]]:
        vcard_data = []
        file_paths = []

        for filename in os.listdir(directory):
            if filename.endswith('.vcf'):
                file_path = os.path.join(directory, filename)
                vcard = VCardHandler.read_vcard(file_path)
                if vcard:
                    name, email, tel = VCardHandler.extract_key_info(vcard)
                    vcard_data.append(f"{name} {email} {tel}")
                    file_paths.append(file_path)

        if not vcard_data:
            logger.warning("No valid vCard files found in the directory.")
            return {}

        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(vcard_data)

        cosine_sim = cosine_similarity(tfidf_matrix)

        duplicates = defaultdict(list)
        for i in range(len(cosine_sim)):
            for j in range(i+1, len(cosine_sim)):
                sim = cosine_sim[i][j]
                if sim > self.config['similarity_threshold']:
                    duplicates[file_paths[i]].append((file_paths[j], sim))

        logger.info(f"Found {len(duplicates)} potential duplicate sets")
        return duplicates

class DuplicateProcessor:
    def __init__(self, config: Config):
        self.config = config
        self.ai_assistant = AIAssistant(config)

    def process_duplicates(self, duplicates: Dict[str, List[Tuple[str, float]]], directory: str) -> None:
        total_duplicates = sum(len(similar_files) for similar_files in duplicates.values())
        current_duplicate = 0
        ai_merged = 0
        auto_merged = 0

        merge_dir = self.get_merge_directory(directory)
        os.makedirs(merge_dir, exist_ok=True)

        for primary_file, similar_files in duplicates.items():
            primary_vcard = VCardHandler.read_vcard(primary_file)
            if not primary_vcard:
                continue
            primary_name, primary_email, primary_tel = VCardHandler.extract_key_info(primary_vcard)

            for similar_file, similarity in similar_files:
                current_duplicate += 1
                similar_vcard = VCardHandler.read_vcard(similar_file)
                if not similar_vcard:
                    continue
                similar_name, similar_email, similar_tel = VCardHandler.extract_key_info(similar_vcard)

                logger.info(f"Processing duplicate {current_duplicate} of {total_duplicates}")
                logger.debug(f"Primary: {primary_name}, {primary_email}, {primary_tel}")
                logger.debug(f"Similar: {similar_name}, {similar_email}, {similar_tel}")
                logger.debug(f"Similarity: {similarity:.2f}")

                print(f"\n--- Duplicate {current_duplicate} of {total_duplicates} ---")
                print(f"Primary vCard: {os.path.basename(primary_file)}")
                print(f"Name: {primary_name}")
                print(f"Email: {primary_email}")
                print(f"Phone: {primary_tel}")
                print(f"\nPotential duplicate: {os.path.basename(similar_file)}")
                print(f"Name: {similar_name}")
                print(f"Email: {similar_email}")
                print(f"Phone: {similar_tel}")
                print(f"Similarity: {similarity:.2f}")

                merge_successful = False

                if similarity >= self.config['auto_merge_threshold']:
                    print("Similarity above auto-merge threshold. Automatically merging.")
                    merge_successful = self.perform_merge(primary_vcard, similar_vcard, primary_file, directory)
                    if merge_successful:
                        auto_merged += 1
                elif similarity >= self.config['ai_decision_threshold']:
                    should_merge, merge_instructions, ai_response = self.ai_assistant.get_merge_decision(primary_vcard, similar_vcard, similarity)
                    ai_logger.info(f"AI decision for {os.path.basename(primary_file)} and {os.path.basename(similar_file)}:\n{ai_response}")

                    if should_merge:
                        print("AI recommends merging. Proceeding with merge.")
                        merge_successful = self.perform_merge(primary_vcard, similar_vcard, primary_file, directory, merge_instructions)
                        if merge_successful:
                            ai_merged += 1
                    else:
                        print("AI does not recommend merging. Skipping this pair.")
                else:
                    print("Similarity below AI decision threshold. Skipping this pair.")

                # Move original files to merge directory, regardless of merge outcome
                self.move_original_files(primary_file, similar_file, merge_dir)

                # If merge was not successful or not performed, we need to keep a copy of at least one of the original files
                if not merge_successful:
                    self.keep_original_copy(primary_file, merge_dir)

        logger.info(f"Processing complete. Auto-merged: {auto_merged}, AI-merged: {ai_merged}, Total duplicates: {total_duplicates}")
        print(f"\nProcessing complete.")
        print(f"Auto-merged: {auto_merged}")
        print(f"AI-merged: {ai_merged}")
        print(f"Total potential duplicates: {total_duplicates}")
        print(f"Unmerged files can be found in: {merge_dir}")

    def get_merge_directory(self, source_dir: str) -> str:
        base_merge_dir = self.config['merged_dir']
        dir_hash = hashlib.md5(source_dir.encode()).hexdigest()[:8]
        merge_dir = os.path.join(base_merge_dir, dir_hash)
        logger.info(f"Merge directory for unmerged files: {merge_dir}")
        return merge_dir

    def perform_merge(self, primary_vcard: vobject.vCard, similar_vcard: vobject.vCard, primary_file: str, directory: str, merge_instructions: Optional[Dict] = None) -> bool:
        try:
            merged_vcard = VCardHandler.merge_vcards(primary_vcard, similar_vcard, merge_instructions)
            if merged_vcard:
                merged_filename = f"merged_{os.path.basename(primary_file)}"
                merged_path = os.path.join(directory, merged_filename)

                serialized_vcard = VCardHandler.serialize_vcard(merged_vcard)
                if serialized_vcard:
                    with open(merged_path, 'w', encoding='utf-8') as f:
                        f.write(serialized_vcard)
                    logger.info(f"Merged vCard saved to {merged_path}")
                    print(f"Merged vCard saved to {merged_path}")
                    return True
                else:
                    logger.error("Failed to serialize merged vCard. Printing debug information:")
                    print("Error: Failed to serialize merged vCard. Debug information:")
                    debug_info = VCardHandler.debug_vcard(merged_vcard)
                    logger.error(debug_info)
                    print(debug_info)
            else:
                logger.error("Failed to merge vCards. Printing debug information for both vCards:")
                print("Error: Failed to merge vCards. Debug information for both vCards:")
                primary_debug = VCardHandler.debug_vcard(primary_vcard)
                similar_debug = VCardHandler.debug_vcard(similar_vcard)
                logger.error(f"Primary vCard:\n{primary_debug}\n\nSimilar vCard:\n{similar_debug}")
                print(f"Primary vCard:\n{primary_debug}\n\nSimilar vCard:\n{similar_debug}")
        except Exception as e:
            logger.error(f"Error during merge process: {str(e)}")
            print(f"Error during merge process: {str(e)}")
            logger.error("Printing debug information for both vCards:")
            print("Debug information for both vCards:")
            primary_debug = VCardHandler.debug_vcard(primary_vcard)
            similar_debug = VCardHandler.debug_vcard(similar_vcard)
            logger.error(f"Primary vCard:\n{primary_debug}\n\nSimilar vCard:\n{similar_debug}")
            print(f"Primary vCard:\n{primary_debug}\n\nSimilar vCard:\n{similar_debug}")
        return False

    def move_original_files(self, primary_file: str, similar_file: str, merge_dir: str) -> None:
        try:
            os.rename(primary_file, os.path.join(merge_dir, os.path.basename(primary_file)))
            os.rename(similar_file, os.path.join(merge_dir, os.path.basename(similar_file)))
            logger.info(f"Moved original files to {merge_dir}")
            print(f"Original files moved to {merge_dir}")
        except Exception as e:
            logger.error(f"Error moving original files: {str(e)}")
            print(f"Error moving original files: {str(e)}")

    def keep_original_copy(self, primary_file: str, merge_dir: str) -> None:
        try:
            shutil.copy2(os.path.join(merge_dir, os.path.basename(primary_file)), primary_file)
            logger.info(f"Kept a copy of {os.path.basename(primary_file)} in the original directory")
            print(f"Kept a copy of {os.path.basename(primary_file)} in the original directory")
        except Exception as e:
            logger.error(f"Error keeping a copy of the original file: {str(e)}")
            print(f"Error keeping a copy of the original file: {str(e)}")

def main():
    # Ensure OpenAI API key is set
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OpenAI API key not found. Please set OPENAI_API_KEY in your .env file.")
        print("Error: OpenAI API key not found. Please set OPENAI_API_KEY in your .env file.")
        sys.exit(1)

    config = Config()

    # Check for command-line argument
    if len(sys.argv) > 1:
        directory = sys.argv[1]
    else:
        directory = input("Enter the directory path containing vCard files: ")

    logger.info(f"Scanning directory: {directory}")

    duplicate_finder = DuplicateFinder(config)
    duplicates = duplicate_finder.find_duplicates_ml(directory)

    if duplicates:
        total_duplicates = sum(len(similar_files) for similar_files in duplicates.values())
        logger.info(f"Found {total_duplicates} potential duplicates. Starting processing.")
        print(f"\nFound {total_duplicates} potential duplicates. Starting processing.")

        duplicate_processor = DuplicateProcessor(config)
        duplicate_processor.process_duplicates(duplicates, directory)
    else:
        logger.info("No potential duplicates found.")
        print("No potential duplicates found.")

if __name__ == "__main__":
    main()

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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Config:
    def __init__(self, config_path: str = 'vcard_dupechecker_config.yaml'):
        self.default_config = {
            'similarity_threshold': 0.8,
            'auto_merge_threshold': 0.95,
            'keep_originals': False,
            'merged_dir': 'merged_vcards'
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
    def merge_vcards(vcard1: vobject.vCard, vcard2: vobject.vCard) -> Optional[vobject.vCard]:
        try:
            merged = vobject.vCard()

            def copy_prop(prop):
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

        if hasattr(vcard, 'fn'):
            lines.append(f"FN:{vcard.fn.value}")

        if hasattr(vcard, 'n'):
            n_values = ';'.join(str(value) for value in vcard.n.value)
            lines.append(f"N:{n_values}")

        for prop in ['email', 'tel', 'adr']:
            if hasattr(vcard, prop):
                for item in getattr(vcard, prop + '_list'):
                    lines.append(f"{prop.upper()}:{item.value}")

        if hasattr(vcard, 'org'):
            org_value = vcard.org.value[0] if vcard.org.value else ''
            lines.append(f"ORG:{org_value}")

        if hasattr(vcard, 'title'):
            lines.append(f"TITLE:{vcard.title.value}")

        if hasattr(vcard, 'note'):
            lines.append(f"NOTE:{vcard.note.value}")

        lines.append("END:VCARD")
        return "\n".join(lines)

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

    def process_duplicates(self, duplicates: Dict[str, List[Tuple[str, float]]], directory: str) -> None:
        total_duplicates = sum(len(similar_files) for similar_files in duplicates.values())
        current_duplicate = 0
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

                if similarity > self.config['auto_merge_threshold']:
                    print("Auto-merging due to high similarity.")
                    merge_choice = 'y'
                    auto_merged += 1
                else:
                    merge_choice = input("Do you want to merge these vCards? (y/n): ").lower()

                merge_successful = False
                if merge_choice == 'y':
                    merge_successful = self.perform_merge(primary_vcard, similar_vcard, primary_file, directory)

                # Move original files to merge directory, regardless of merge outcome
                self.move_original_files(primary_file, similar_file, merge_dir)

                # If merge was not successful, we need to keep a copy of at least one of the original files
                if not merge_successful:
                    self.keep_original_copy(primary_file, merge_dir)

        logger.info(f"Processing complete. Auto-merged {auto_merged} out of {total_duplicates} duplicates.")
        print(f"\nProcessing complete. Auto-merged {auto_merged} out of {total_duplicates} duplicates.")
        print(f"Unmerged files can be found in: {merge_dir}")

    def get_merge_directory(self, source_dir: str) -> str:
        base_merge_dir = self.config['merged_dir']
        dir_hash = hashlib.md5(source_dir.encode()).hexdigest()[:8]
        merge_dir = os.path.join(base_merge_dir, dir_hash)
        logger.info(f"Merge directory for unmerged files: {merge_dir}")
        return merge_dir

    def perform_merge(self, primary_vcard: vobject.vCard, similar_vcard: vobject.vCard, primary_file: str, directory: str) -> bool:
        try:
            merged_vcard = VCardHandler.merge_vcards(primary_vcard, similar_vcard)
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
                    logger.error("Failed to serialize merged vCard. Skipping this merge.")
                    print("Error: Failed to serialize merged vCard. Skipping this merge.")
            else:
                logger.error("Failed to merge vCards. Skipping this merge.")
                print("Error: Failed to merge vCards. Skipping this merge.")
        except Exception as e:
            logger.error(f"Error during merge process: {str(e)}")
            print(f"Error during merge process: {str(e)}")
            print("Skipping this merge due to error.")
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

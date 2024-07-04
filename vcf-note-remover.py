#!/usr/bin/env python3
"""
VCF Note Remover

This script processes vCard (.vcf) files in a specified directory, removing the NOTE field
unless it contains specific keywords defined in a YAML configuration file.

Usage:
    python vcf-note-remover.py [-h] [-c CONFIG] [-v] directory

Arguments:
    directory            Path to the directory containing vCard files

Options:
    -h, --help           Show this help message and exit
    -c CONFIG, --config CONFIG
                         Path to the YAML configuration file (default: vcard-note-remover-config.yaml)
    -v, --verbose        Enable verbose output for debugging

Requirements:
    - Python 3.6+
    - vobject library (install with: pip install vobject)
    - PyYAML library (install with: pip install PyYAML)

Author: Assistant
Date: 2023-07-04
Version: 1.0
"""

import os
import argparse
import logging
import yaml
import vobject
from typing import List, Dict

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config(config_path: str) -> Dict:
    """
    Load the YAML configuration file.

    Args:
        config_path (str): Path to the YAML configuration file

    Returns:
        Dict: Configuration settings

    Raises:
        FileNotFoundError: If the configuration file is not found
        yaml.YAMLError: If there's an error parsing the YAML file
    """
    try:
        with open(config_path, 'r') as config_file:
            config = yaml.safe_load(config_file)
        logger.info(f"Configuration loaded from {config_path}")
        logger.debug(f"Configuration: {config}")
        return config
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML configuration: {e}")
        raise

def should_keep_note(note: str, keywords: List[str]) -> bool:
    """
    Determine if a note should be kept based on the presence of keywords.

    Args:
        note (str): The note content
        keywords (List[str]): List of keywords to check for

    Returns:
        bool: True if the note contains any of the keywords, False otherwise
    """
    return any(keyword.lower() in note.lower() for keyword in keywords)

def process_vcard(vcard_path: str, keywords: List[str]) -> bool:
    """
    Process a single vCard file, removing the NOTE field if it doesn't contain keywords.

    Args:
        vcard_path (str): Path to the vCard file
        keywords (List[str]): List of keywords to check for in the NOTE field

    Returns:
        bool: True if the vCard was modified, False otherwise

    Raises:
        IOError: If there's an error reading or writing the vCard file
        vobject.base.ParseError: If there's an error parsing the vCard
    """
    try:
        with open(vcard_path, 'r', encoding='utf-8') as f:
            vcard = vobject.readOne(f.read())

        logger.debug(f"Processing vCard: {vcard_path}")

        if 'note' not in vcard.contents:
            logger.debug(f"No NOTE field found in {vcard_path}")
            return False

        note = vcard.note.value
        if should_keep_note(note, keywords):
            logger.info(f"Keeping note in {vcard_path} (contains keyword)")
            logger.debug(f"Note content: {note}")
            return False
        else:
            logger.info(f"Removing note from {vcard_path}")
            del vcard.note
            with open(vcard_path, 'w', encoding='utf-8') as f:
                f.write(vcard.serialize())
            return True

    except IOError as e:
        logger.error(f"IOError processing {vcard_path}: {e}")
        raise
    except vobject.base.ParseError as e:
        logger.error(f"ParseError processing {vcard_path}: {e}")
        raise

def process_directory(directory: str, keywords: List[str]) -> Dict[str, int]:
    """
    Process all vCard files in the specified directory.

    Args:
        directory (str): Path to the directory containing vCard files
        keywords (List[str]): List of keywords to check for in the NOTE field

    Returns:
        Dict[str, int]: Statistics about the processed vCards
    """
    stats = {"total": 0, "modified": 0, "errors": 0}

    for filename in os.listdir(directory):
        if filename.lower().endswith('.vcf'):
            vcard_path = os.path.join(directory, filename)
            stats["total"] += 1

            try:
                if process_vcard(vcard_path, keywords):
                    stats["modified"] += 1
            except (IOError, vobject.base.ParseError):
                stats["errors"] += 1

    logger.info(f"Processed {stats['total']} vCards")
    logger.info(f"Modified {stats['modified']} vCards")
    logger.info(f"Encountered {stats['errors']} errors")

    return stats

def main():
    parser = argparse.ArgumentParser(description="Remove NOTE fields from vCard files")
    parser.add_argument("directory", help="Path to the directory containing vCard files")
    parser.add_argument("-c", "--config", default="vcard-note-remover-config.yaml", help="Path to the YAML configuration file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output for debugging")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    try:
        config = load_config(args.config)
        keywords = config.get('keywords', [])

        if not keywords:
            logger.warning("No keywords specified in the configuration. All notes will be removed.")

        if not os.path.isdir(args.directory):
            logger.error(f"Invalid directory path: {args.directory}")
            return

        stats = process_directory(args.directory, keywords)
        print(f"Total vCards processed: {stats['total']}")
        print(f"vCards modified: {stats['modified']}")
        print(f"Errors encountered: {stats['errors']}")

    except (FileNotFoundError, yaml.YAMLError) as e:
        logger.error(f"Error with configuration file: {e}")
        return

if __name__ == "__main__":
    main()

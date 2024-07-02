#!/usr/bin/env python3
"""
VCard Sorter

This script sorts vCard (.vcf) files based on whether they contain contact information
(email, phone number, or physical address). Cards without this information are moved
to a separate folder.

Usage:
    python vcard_sorter.py [-h] [-v] [-d] source destination

Arguments:
    source       Source directory containing vCard files
    destination  Destination directory for vCards without contact info

Options:
    -h, --help     Show this help message and exit
    -v, --verbose  Enable verbose output
    -d, --dry-run  Perform a dry run without moving files

Requirements:
    - Python 3.6+
    - vobject library (install with: pip install vobject)
"""

import os
import vobject
import shutil
import argparse
import logging
from typing import Dict, Any

def setup_logging(verbose: bool) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')

def has_contact_info(vcard: vobject.vCard) -> bool:
    """
    Check if a vCard has any contact information.

    Args:
        vcard (vobject.vCard): A vCard object to check

    Returns:
        bool: True if the vCard has a phone number, email, or address; False otherwise
    """
    has_phone = any(tel.value for tel in vcard.contents.get('tel', []))
    has_email = any(email.value for email in vcard.contents.get('email', []))
    has_address = any(adr.value for adr in vcard.contents.get('adr', []))

    logging.debug(f"VCard info - Phone: {has_phone}, Email: {has_email}, Address: {has_address}")
    return has_phone or has_email or has_address

def sort_vcards(source_folder: str, destination_folder: str, dry_run: bool = False) -> Dict[str, int]:
    """
    Sort vCards from the source folder to the destination folder if they lack contact info.

    Args:
        source_folder (str): Path to the folder containing source vCard files
        destination_folder (str): Path to the folder where vCards without contact info will be moved
        dry_run (bool): If True, perform a dry run without moving files

    Returns:
        Dict[str, int]: A dictionary containing statistics about the sorting process
    """
    if not os.path.exists(destination_folder) and not dry_run:
        logging.info(f"Creating destination folder: {destination_folder}")
        os.makedirs(destination_folder)

    stats = {"total_files": 0, "moved_files": 0, "errors": 0}

    for filename in os.listdir(source_folder):
        if filename.lower().endswith('.vcf'):
            stats["total_files"] += 1
            file_path = os.path.join(source_folder, filename)
            logging.debug(f"Processing file: {filename}")

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    vcard = vobject.readOne(f)

                if not has_contact_info(vcard):
                    dest_path = os.path.join(destination_folder, filename)
                    if not dry_run:
                        shutil.move(file_path, dest_path)
                        logging.info(f"Moved {filename} to {destination_folder}")
                    else:
                        logging.info(f"Would move {filename} to {destination_folder}")
                    stats["moved_files"] += 1
                else:
                    logging.debug(f"Keeping {filename} in source folder")
            except Exception as e:
                logging.error(f"Error processing {filename}: {str(e)}")
                stats["errors"] += 1

    return stats

def main() -> None:
    parser = argparse.ArgumentParser(description="Sort vCards based on contact information.")
    parser.add_argument("source", help="Source directory containing vCard files")
    parser.add_argument("destination", help="Destination directory for vCards without contact info")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("-d", "--dry-run", action="store_true", help="Perform a dry run without moving files")
    args = parser.parse_args()

    setup_logging(args.verbose)

    logging.info(f"Starting vCard sorting process")
    logging.info(f"Source folder: {args.source}")
    logging.info(f"Destination folder: {args.destination}")

    if args.dry_run:
        logging.info("Performing dry run - no files will be moved")

    stats = sort_vcards(args.source, args.destination, args.dry_run)

    logging.info("vCard sorting process completed")
    logging.info(f"Processed {stats['total_files']} files. Moved {stats['moved_files']} files. Encountered {stats['errors']} errors.")

if __name__ == "__main__":
    main()

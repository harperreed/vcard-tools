#!/usr/bin/env python3
"""
VCard UID Adder

This script processes vCard (.vcf) files in a specified directory (non-recursively).
It adds a UUID (Universally Unique Identifier) to any vCard that doesn't already have one.

Usage:
    python vcard_uid_adder.py <directory>

Arguments:
    directory   Directory containing vCard files (required)

Options:
    -h, --help     Show this help message and exit
    -v, --verbose  Enable verbose output

Requirements:
    - Python 3.6+
    - vobject library (install with `pip install vobject`)

Author: [Your Name]
Date: [Current Date]
Version: 1.2
"""

import os
import uuid
import vobject
import argparse
import logging
import sys
from typing import Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def add_uid_to_vcard(file_path: str) -> Optional[str]:
    """
    Add a UUID to a vCard file if it doesn't already have one.

    Args:
    file_path (str): The path to the vCard file.

    Returns:
    Optional[str]: The new UUID if one was added, None otherwise.

    Raises:
    IOError: If there's an issue reading or writing the file.
    vobject.base.ParseError: If the vCard file is invalid.
    """
    logger.debug(f"Processing file: {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            vcard = vobject.readOne(f.read())

        if 'uid' not in vcard.contents:
            new_uid = str(uuid.uuid4())
            logger.info(f"Adding new UID {new_uid} to {file_path}")
            vcard.add('uid').value = new_uid

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(vcard.serialize())

            logger.debug(f"Successfully updated {file_path}")
            return new_uid
        else:
            logger.debug(f"UID already exists in {file_path}")
            return None

    except IOError as e:
        logger.error(f"IO error occurred while processing {file_path}: {e}")
        raise
    except vobject.base.ParseError as e:
        logger.error(f"Parse error occurred while processing {file_path}: {e}")
        raise

def process_directory(directory: str) -> dict:
    """
    Process all .vcf files in the given directory (non-recursively).

    Args:
    directory (str): The path to the directory containing vCard files.

    Returns:
    dict: A summary of the processing results.
    """
    summary = {"processed": 0, "updated": 0, "errors": 0}

    logger.info(f"Starting to process directory: {directory}")

    for file in os.listdir(directory):
        if file.lower().endswith('.vcf'):
            file_path = os.path.join(directory, file)
            summary["processed"] += 1

            try:
                result = add_uid_to_vcard(file_path)
                if result:
                    summary["updated"] += 1
            except (IOError, vobject.base.ParseError) as e:
                logger.error(f"Error processing {file_path}: {e}")
                summary["errors"] += 1

    logger.info(f"Finished processing directory: {directory}")
    return summary

def main(args=None):
    """
    Main function to run the script.
    """
    parser = argparse.ArgumentParser(
        description="Add UIDs to vCard files in a directory (non-recursively).",
        usage="%(prog)s <directory> [-v]"
    )
    parser.add_argument("directory", help="Directory containing vCard files")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    if args is None:
        args = sys.argv[1:]

    if not args:
        parser.print_help()
        return

    args = parser.parse_args(args)

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    directory = os.path.abspath(args.directory)
    logger.info(f"Processing vCards in directory: {directory}")

    summary = process_directory(directory)

    logger.info("Processing complete. Summary:")
    logger.info(f"  Files processed: {summary['processed']}")
    logger.info(f"  Files updated: {summary['updated']}")
    logger.info(f"  Errors encountered: {summary['errors']}")

if __name__ == "__main__":
    main()

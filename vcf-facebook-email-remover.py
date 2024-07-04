#!/usr/bin/env python3

import os
import vobject
import argparse
import logging
from typing import List, Tuple

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def remove_facebook_emails(vcard: vobject.vCard) -> Tuple[vobject.vCard, int]:
    """
    Remove email addresses ending with @facebook.com from a vCard.

    Args:
    vcard (vobject.vCard): The vCard to process.

    Returns:
    Tuple[vobject.vCard, int]: The processed vCard and the number of removed emails.
    """
    removed_count = 0
    if hasattr(vcard, 'email_list'):
        new_email_list = []
        for email in vcard.email_list:
            if not email.value.lower().endswith('@facebook.com'):
                new_email_list.append(email)
            else:
                removed_count += 1

        vcard.email_list.clear()
        for email in new_email_list:
            vcard.add('email')
            vcard.email_list[-1].value = email.value

    return vcard, removed_count

def process_vcard_file(file_path: str) -> Tuple[int, int]:
    """
    Process a single vCard file.

    Args:
    file_path (str): Path to the vCard file.

    Returns:
    Tuple[int, int]: Number of vCards processed and number of emails removed.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        vcards = vobject.readComponents(content)

        total_removed = 0
        processed_vcards = []

        for vcard in vcards:
            processed_vcard, removed_count = remove_facebook_emails(vcard)
            processed_vcards.append(processed_vcard)
            total_removed += removed_count

        if total_removed > 0:
            with open(file_path, 'w', encoding='utf-8') as f:
                for vcard in processed_vcards:
                    f.write(vcard.serialize())
            logger.info(f"Processed {file_path}: Removed {total_removed} Facebook email(s)")
        else:
            logger.info(f"Processed {file_path}: No Facebook emails found")

        return len(processed_vcards), total_removed
    except vobject.base.ParseError as e:
        logger.error(f"Error parsing {file_path}: {str(e)}")
        return 0, 0
    except IOError as e:
        logger.error(f"I/O error processing {file_path}: {str(e)}")
        return 0, 0
    except Exception as e:
        logger.error(f"Unexpected error processing {file_path}: {str(e)}")
        return 0, 0

def process_directory(directory: str) -> Tuple[int, int, int]:
    """
    Process all vCard files in a directory.

    Args:
    directory (str): Path to the directory containing vCard files.

    Returns:
    Tuple[int, int, int]: Number of files processed, total vCards processed, and total emails removed.
    """
    files_processed = 0
    total_vcards_processed = 0
    total_emails_removed = 0

    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.vcf'):
                file_path = os.path.join(root, file)
                vcards_processed, emails_removed = process_vcard_file(file_path)
                files_processed += 1
                total_vcards_processed += vcards_processed
                total_emails_removed += emails_removed

    return files_processed, total_vcards_processed, total_emails_removed

def main():
    parser = argparse.ArgumentParser(description="Remove @facebook.com email addresses from vCard files.")
    parser.add_argument("directory", help="Directory containing vCard files")
    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        logger.error(f"The specified directory does not exist: {args.directory}")
        return

    logger.info(f"Processing vCards in directory: {args.directory}")
    files_processed, vcards_processed, emails_removed = process_directory(args.directory)

    logger.info(f"Processing complete.")
    logger.info(f"Files processed: {files_processed}")
    logger.info(f"vCards processed: {vcards_processed}")
    logger.info(f"Facebook emails removed: {emails_removed}")

if __name__ == "__main__":
    main()

import os
import re
import logging
import argparse
import vobject

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def remove_obsolete_items(content):
    """Remove all items labeled as obsolete and their related entries from a vCard content."""
    lines = content.split('\n')
    cleaned_lines = []
    obsolete_items = set()

    # First pass: identify obsolete items
    for line in lines:
        match = re.match(r'item(\d+)\.X-ABLABEL:\s*obsolete', line, re.IGNORECASE)
        if match:
            obsolete_items.add(match.group(1))
            logger.debug(f"Identified obsolete item: {match.group(1)}")

    # Second pass: remove obsolete items and their related entries
    for line in lines:
        skip = False
        for item in obsolete_items:
            if line.startswith(f'item{item}.'):
                skip = True
                logger.debug(f"Removed line: {line}")
                break
        if not skip:
            cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)

def process_vcard_file(file_path):
    """Process a single vCard file."""
    logger.info(f"Processing file: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        cleaned_content = remove_obsolete_items(content)

        if original_content != cleaned_content:
            logger.info(f"Changes detected in {file_path}")

            # Process with vobject
            try:
                vcard = vobject.readOne(cleaned_content)
                final_content = vcard.serialize()

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(final_content)
                logger.info(f"Removed obsolete items and saved vCard using vobject: {file_path}")
            except vobject.base.ParseError as ve:
                logger.error(f"vObject parsing error in {file_path}: {str(ve)}")
                logger.info("Saving cleaned content without vobject processing.")
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(cleaned_content)
        else:
            logger.info(f"No obsolete items found in {file_path}")
    except Exception as e:
        logger.error(f"Error processing {file_path}: {str(e)}", exc_info=True)

def process_directory(directory):
    """Process all vCard files in the given directory."""
    logger.info(f"Processing directory: {directory}")
    for filename in os.listdir(directory):
        if filename.endswith('.vcf'):
            file_path = os.path.join(directory, filename)
            process_vcard_file(file_path)

def main():
    parser = argparse.ArgumentParser(description="Remove obsolete items from vCard files.")
    parser.add_argument("directory", help="Directory containing vCard files")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    if os.path.isdir(args.directory):
        process_directory(args.directory)
        print("Processing complete. Check the log for details.")
    else:
        print("Invalid directory path. Please try again.")

if __name__ == "__main__":
    main()

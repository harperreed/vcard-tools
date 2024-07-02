#!/usr/bin/env python3

import argparse
import os
import pathlib
import logging
from typing import List, Optional, Tuple, Dict
import vobject
import re
import uuid

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VCardProcessor:
    def __init__(self, content_filter: Optional[str] = None):
        self.content_filter = content_filter

    def guess_name_from_email(self, email: str) -> str:
        """Guess a name from an email address."""
        local_part = email.split('@')[0]
        name = re.sub(r'[._]', ' ', local_part)
        return ' '.join(word.capitalize() for word in name.split())

    def process_vcard(self, component: vobject.base.Component) -> Tuple[vobject.vCard, bool]:
        """Process a single vCard component."""
        vcard = component if hasattr(component, 'behavior') else vobject.vCard()

        if not hasattr(component, 'behavior'):
            for key, value_list in component.contents.items():
                for value in value_list:
                    vcard.add(key).value = value.value

        is_valid = self.validate_and_fix_vcard(vcard)

        # Ensure the vCard has a UID
        if 'uid' not in vcard.contents:
            vcard.add('uid').value = str(uuid.uuid4())

        return vcard, is_valid

    def validate_and_fix_vcard(self, vcard: vobject.vCard) -> bool:
        """Validate and fix a vCard if possible."""
        is_valid = True
        if 'fn' not in vcard.contents:
            if 'email' in vcard.contents:
                guessed_name = self.guess_name_from_email(vcard.email.value)
                vcard.add('fn').value = guessed_name
                logger.info(f"Added guessed name '{guessed_name}' from email '{vcard.email.value}'")
            else:
                vcard.add('fn').value = "Unknown"
                logger.warning("Entry missing FN and email: marked as invalid")
                is_valid = False
        return is_valid

    def split_vcf(self, fpath: str) -> List[Tuple[vobject.vCard, bool]]:
        """Split the content of a VCF file into a list of tuples."""
        try:
            with open(fpath, 'r') as f:
                content = f.read()

            vcards = []
            for component in vobject.readComponents(content):
                try:
                    vcard, is_valid = self.process_vcard(component)
                    if self.content_filter is None or self.content_filter in vcard.serialize():
                        vcards.append((vcard, is_valid))
                except Exception as e:
                    logger.warning(f"Error processing VCARD entry: {e}")
                    vcards.append((component, False))

            logger.info(f"Successfully split {fpath} into {len(vcards)} VCARD entries")
            return vcards
        except IOError as e:
            logger.error(f"Error reading file {fpath}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error parsing VCF file {fpath}: {e}")
            raise ValueError(f"Invalid VCF file: {e}")

class VCardWriter:
    def __init__(self, outdir: pathlib.Path):
        self.outdir = outdir

    def write_vcard(self, vcard: vobject.vCard, is_valid: bool) -> bool:
        """Write the content of a VCARD using its UID as the filename."""
        try:
            uid = vcard.uid.value
            suffix = "_invalid" if not is_valid else ""
            filename = self.outdir.joinpath(f"{uid}{suffix}.vcf")

            # Handle potential UID collisions
            counter = 1
            while filename.exists():
                new_uid = f"{uid}_{counter}"
                filename = self.outdir.joinpath(f"{new_uid}{suffix}.vcf")
                counter += 1
                if counter == 1:
                    logger.warning(f"UID collision detected for {uid}. Appending counter to filename.")

            with open(filename, "w") as out:
                out.write(vcard.serialize())
            logger.info(f"Successfully wrote VCARD to {filename}")
            return True
        except IOError as e:
            logger.error(f"Error writing VCARD: {e}")
            return False

def process_files(input_files: List[str], processor: VCardProcessor, writer: VCardWriter) -> Dict[str, int]:
    """Process all input files and write the results."""
    stats = {"total": 0, "valid": 0, "invalid": 0}
    for input_file in input_files:
        logger.info(f"Processing file: {input_file}")
        try:
            for vcard, is_valid in processor.split_vcf(input_file):
                if writer.write_vcard(vcard, is_valid):
                    stats["total"] += 1
                    if is_valid:
                        stats["valid"] += 1
                    else:
                        stats["invalid"] += 1
        except (IOError, ValueError) as e:
            logger.error(f"Error processing {input_file}: {e}")
    return stats

def main():
    """Main function to handle command-line arguments and process VCF files."""
    parser = argparse.ArgumentParser(
        description="A script for splitting multi-entry VCF files into single entry VCard files.",
        epilog="The single entry file names are generated using the UID of each vCard."
    )
    parser.add_argument("input_files", help="List of input files in VCARD format", nargs="+")
    parser.add_argument("-o", "--outdir", help="Output directory to extract the files", required=True, type=pathlib.Path)
    parser.add_argument("-f", "--filter", help="Filter the entries containing %(metavar)s", metavar="STRING")
    parser.add_argument("-v", "--verbose", help="Increase output verbosity", action="store_true")

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    if not args.outdir.exists():
        logger.error(f"Output directory {args.outdir} does not exist")
        parser.error(f"Output directory {args.outdir} does not exist")
    elif not args.outdir.is_dir():
        logger.error(f"Requested output directory {args.outdir} is not a directory")
        parser.error(f"Requested output directory {args.outdir} is not a directory")

    processor = VCardProcessor(args.filter)
    writer = VCardWriter(args.outdir)
    stats = process_files(args.input_files, processor, writer)

    logger.info(f"Processed {len(args.input_files)} input file(s)")
    logger.info(f"Total entries: {stats['total']}")
    logger.info(f"Valid entries: {stats['valid']}")
    logger.info(f"Invalid entries: {stats['invalid']}")

if __name__ == "__main__":
    main()

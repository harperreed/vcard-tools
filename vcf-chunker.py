#!/usr/bin/env python3
"""
VCard File Splitter

This script splits a large VCard (.vcf) file into smaller chunks of a specified size.
It's particularly useful for breaking down large contact lists into manageable sizes
for importing into services like Google Contacts.

Usage:
    python vcard_splitter.py <input_file> <output_directory> [--chunk-size <size_in_mb>] [--debug]

Arguments:
    input_file          Path to the large VCard file to be split
    output_directory    Directory where the split VCard files will be saved

Options:
    --chunk-size <size_in_mb>    Size of each chunk in megabytes (default: 10)
    --debug                      Enable debug logging

Author: [Your Name]
Date: [Current Date]
Version: 1.1
"""

import os
import math
import argparse
import logging
from typing import List

def setup_logging(debug: bool = False) -> None:
    """
    Set up logging configuration.

    Args:
        debug (bool): If True, set logging level to DEBUG. Otherwise, set to INFO.
    """
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=log_level, 
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

def read_vcard_file(input_file: str) -> str:
    """
    Read the content of the input VCard file.

    Args:
        input_file (str): Path to the input VCard file.

    Returns:
        str: Content of the VCard file.

    Raises:
        FileNotFoundError: If the input file doesn't exist.
        IOError: If there's an error reading the file.
    """
    logging.info(f"Reading input file: {input_file}")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        logging.debug(f"Successfully read {len(content)} characters from the input file.")
        return content
    except FileNotFoundError:
        logging.error(f"Input file not found: {input_file}")
        raise
    except IOError as e:
        logging.error(f"Error reading input file: {e}")
        raise

def split_into_vcards(content: str) -> List[str]:
    """
    Split the content into individual VCard entries.

    Args:
        content (str): The entire content of the VCard file.

    Returns:
        List[str]: A list of individual VCard entries.
    """
    logging.info("Splitting content into individual VCards")
    vcards = content.split('END:VCARD\n')
    vcards = [vcard.strip() + '\nEND:VCARD\n' for vcard in vcards if vcard.strip()]
    logging.debug(f"Found {len(vcards)} individual VCard entries")
    return vcards

def write_chunk(chunk: List[str], output_file: str) -> None:
    """
    Write a chunk of VCards to an output file.

    Args:
        chunk (List[str]): List of VCard entries to write.
        output_file (str): Path to the output file.

    Raises:
        IOError: If there's an error writing the file.
    """
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(''.join(chunk))
        logging.info(f"Created chunk: {output_file}")
        logging.debug(f"Wrote {len(chunk)} VCards to {output_file}")
    except IOError as e:
        logging.error(f"Error writing chunk to {output_file}: {e}")
        raise

def split_vcard_file(input_file: str, output_directory: str, chunk_size_mb: int = 10) -> None:
    """
    Split a large VCard file into smaller chunks.

    Args:
        input_file (str): Path to the input VCard file.
        output_directory (str): Directory to save the split VCard files.
        chunk_size_mb (int): Desired size of each chunk in megabytes.

    Raises:
        ValueError: If chunk_size_mb is not positive.
    """
    if chunk_size_mb <= 0:
        logging.error("Chunk size must be a positive number")
        raise ValueError("Chunk size must be a positive number")

    # Convert chunk size to bytes
    chunk_size = chunk_size_mb * 1024 * 1024

    # Ensure output directory exists
    os.makedirs(output_directory, exist_ok=True)
    logging.info(f"Output directory: {output_directory}")

    content = read_vcard_file(input_file)
    vcards = split_into_vcards(content)

    total_size = len(content.encode('utf-8'))
    num_chunks = math.ceil(total_size / chunk_size)
    logging.info(f"Total size: {total_size} bytes")
    logging.info(f"Estimated number of chunks: {num_chunks}")

    current_chunk = []
    current_size = 0
    chunk_number = 1

    for vcard in vcards:
        vcard_size = len(vcard.encode('utf-8'))
        if current_size + vcard_size > chunk_size and current_chunk:
            # Write current chunk to file
            output_file = os.path.join(output_directory, f'contacts_chunk_{chunk_number}.vcf')
            write_chunk(current_chunk, output_file)
            
            # Start a new chunk
            current_chunk = [vcard]
            current_size = vcard_size
            chunk_number += 1
        else:
            current_chunk.append(vcard)
            current_size += vcard_size
        
        logging.debug(f"Processed VCard: {vcard[:50]}... (size: {vcard_size} bytes)")

    # Write the last chunk if there's any data left
    if current_chunk:
        output_file = os.path.join(output_directory, f'contacts_chunk_{chunk_number}.vcf')
        write_chunk(current_chunk, output_file)

    logging.info(f"Splitting complete. Created {chunk_number} chunks.")

def main():
    """
    Main function to handle command-line arguments and execute the script.
    """
    parser = argparse.ArgumentParser(description="Split a large VCard file into smaller chunks.")
    parser.add_argument("input_file", help="Path to the large VCard file to be split")
    parser.add_argument("output_directory", help="Directory where the split VCard files will be saved")
    parser.add_argument("--chunk-size", type=int, default=10, help="Size of each chunk in megabytes (default: 10)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    setup_logging(args.debug)

    logging.info("Starting VCard file splitting process")
    logging.info(f"Input file: {args.input_file}")
    logging.info(f"Output directory: {args.output_directory}")
    logging.info(f"Chunk size: {args.chunk_size} MB")

    try:
        split_vcard_file(args.input_file, args.output_directory, args.chunk_size)
        logging.info("VCard splitting process completed successfully")
    except Exception as e:
        logging.error(f"An error occurred during the splitting process: {e}")
        raise

if __name__ == "__main__":
    main()

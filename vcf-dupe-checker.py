import os
import vobject
from collections import defaultdict

def read_vcard(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return vobject.readOne(f.read())

def extract_key_info(vcard):
    # Extract name and email as key identifiers
    name = str(vcard.fn.value) if hasattr(vcard, 'fn') else ''
    email = str(vcard.email.value) if hasattr(vcard, 'email') else ''
    return (name, email)

def find_duplicates(directory):
    duplicates = defaultdict(list)
    
    for filename in os.listdir(directory):
        if filename.endswith('.vcf'):
            file_path = os.path.join(directory, filename)
            vcard = read_vcard(file_path)
            key_info = extract_key_info(vcard)
            duplicates[key_info].append(filename)
    
    return {k: v for k, v in duplicates.items() if len(v) > 1}

def main():
    directory = input("Enter the directory path containing vCard files: ")
    duplicate_groups = find_duplicates(directory)
    
    if duplicate_groups:
        print("Duplicates found:")
        for key, files in duplicate_groups.items():
            print(f"\nName: {key[0]}, Email: {key[1]}")
            print("Duplicate files:")
            for file in files:
                print(f"- {file}")
    else:
        print("No duplicates found.")

if __name__ == "__main__":
    main()

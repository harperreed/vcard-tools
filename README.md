# VCard Tools 📇🔧

[![GitHub](https://img.shields.io/github/license/harperreed/vcard-tools)](https://github.com/harperreed/vcard-tools/blob/main/LICENSE)

This repository contains a collection of Python scripts for managing and manipulating VCard (.vcf) files. The scripts are designed to help with various tasks such as cleaning up, splitting, merging, and deduplicating VCard files. 🎉

## 🚀 Getting Started

To get started with these tools, clone the repository and install the required dependencies:

```bash
git clone https://github.com/harperreed/vcard-tools.git
cd vcard-tools
pip install -r requirements.txt
```

## 🛠️ Tools

Here's an overview of the scripts included in this repository:

### 📥 `vcf-splitter.py`

This script splits multi-entry VCF files into single-entry VCard files. It can also filter entries based on a specified string. 🗂️

### 🔍 `vcf-dupe-checker.py` 

A simple duplicate checker that identifies potential duplicate VCards based on name and email. 👥

### 🔍🤖 `vcf-dupe-checker-ml.py`

An advanced duplicate checker that uses machine learning (TF-IDF and cosine similarity) to identify potential duplicates. It also includes an interactive merging process. 🧠

### 🔍🤖🧠 `vcf-dupe-checker-ai.py`

A state-of-the-art duplicate checker that leverages AI (OpenAI's GPT) to make intelligent decisions about merging potential duplicates. 🤖

### 🧹 `vcf-cleanup.py`

This script helps clean up VCard files by identifying and moving cards that match certain keywords or lack essential information. 🗑️

### 🗂️ `vcf-sort.py`

A script for sorting VCards based on whether they contain contact information (email, phone number, or physical address). 📁

### 🆔 `vcf_uid_adder.py`

Adds a UUID (Universally Unique Identifier) to any VCard that doesn't already have one. 🪪

### 🕵️‍♀️ `vcf-curator.py`

An interactive tool that searches for information about contacts and helps decide which ones to keep or move. 🔍

### 🍰 `vcf-chunker.py`

Splits large VCard files into smaller, more manageable chunks. 🔪

### 🚫 `vcf-facebook-email-remover.py`

Removes email addresses ending with @facebook.com from VCard files. 🙅‍♂️

### 🌅 `vcf-fix-sunshine-obsolete.py`

Fixes VCard files exported from the Sunshine contacts app by removing obsolete items. ☀️

### 📝 `vcf-note-remover.py`

Removes the NOTE field from VCard files unless it contains specific keywords defined in a configuration file. 📋

## 📚 Documentation

Each script includes a detailed docstring explaining its purpose, usage, and dependencies. For more information, refer to the individual script files. 📖

## 🤝 Contributing 

Contributions are welcome! If you have any ideas for improvements or new features, please open an issue or submit a pull request. 🙌

## 📄 License

This project is licensed under the [MIT License](LICENSE). ⚖️

## 🙏 Acknowledgments

Special thanks to the creators and maintainers of the libraries used in this project, including [vobject](https://github.com/eventable/vobject), [scikit-learn](https://scikit-learn.org/), and [OpenAI](https://openai.com/). 🌟

---

Feel free to reach out if you have any questions or feedback! 💬

Happy VCard management! 🎉

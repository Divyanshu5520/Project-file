import os
import itertools
import string
import zipfile
import PyPDF2
from multiprocessing import Pool, cpu_count
from tkinter import Tk, filedialog, simpledialog, messagebox

def select_file():
    """Let the user select a PDF or ZIP file."""
    root = Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="Select a PDF or ZIP file",
        filetypes=[("PDF Files", "*.pdf"), ("ZIP Files", "*.zip")]
    )
    return file_path

def brute_force_attack(file_path, max_length=4, charset=None):
    """Brute-force attack with customizable character set and max length."""
    if charset is None:
        charset = string.ascii_letters + string.digits + string.punctuation

    def try_password(password):
        try:
            if file_path.endswith('.pdf'):
                with open(file_path, 'rb') as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    if pdf_reader.is_encrypted and pdf_reader.decrypt(password):
                        return password
            elif file_path.endswith('.zip'):
                with zipfile.ZipFile(file_path) as zf:
                    zf.extractall(pwd=password.encode())
                    return password
        except:
            pass
        return None

    with Pool(cpu_count()) as pool:
        for length in range(1, max_length + 1):
            for attempt in pool.imap_unordered(
                try_password,
                (''.join(c) for c in itertools.product(charset, repeat=length))
            ):
                if attempt:
                    return attempt
    return None

def dictionary_attack(file_path, wordlist_path='rockyou.txt'):
    """Dictionary attack using a wordlist file."""
    if not os.path.exists(wordlist_path):
        print(f"Wordlist not found: {wordlist_path}")
        return None

    def try_password(password):
        try:
            if file_path.endswith('.pdf'):
                with open(file_path, 'rb') as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    if pdf_reader.is_encrypted and pdf_reader.decrypt(password):
                        return password
            elif file_path.endswith('.zip'):
                with zipfile.ZipFile(file_path) as zf:
                    zf.extractall(pwd=password.encode())
                    return password
        except:
            pass
        return None

    with open(wordlist_path, 'r', errors='ignore') as f:
        for line in f:
            password = line.strip()
            result = try_password(password)
            if result:
                return result
    return None

def mask_attack(file_path, mask):
    """Mask attack (e.g., '?u?l?l?d?d' for 'Aaa11')."""
    from itertools import product

    def generate_from_mask(mask):
        charsets = {
            '?l': string.ascii_lowercase,
            '?u': string.ascii_uppercase,
            '?d': string.digits,
            '?s': string.punctuation
        }
        parts = []
        for c in mask:
            if c in charsets:
                parts.append(charsets[c])
            else:
                parts.append(c)
        return product(*parts)

    for attempt in generate_from_mask(mask):
        password = ''.join(attempt)
        try:
            if file_path.endswith('.pdf'):
                with open(file_path, 'rb') as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    if pdf_reader.is_encrypted and pdf_reader.decrypt(password):
                        return password
            elif file_path.endswith('.zip'):
                with zipfile.ZipFile(file_path) as zf:
                    zf.extractall(pwd=password.encode())
                    return password
        except:
            continue
    return None

def main():
    file_path = select_file()
    if not file_path:
        print("No file selected.")
        return

    print("\nChoose attack type:")
    print("1. Brute-Force Attack")
    print("2. Dictionary Attack")
    print("3. Mask Attack")
    choice = input("Enter your choice (1/2/3): ")

    password = None
    if choice == '1':
        max_length = simpledialog.askinteger("Brute-Force", "Max password length (e.g., 4):", minvalue=1, maxvalue=10)
        if max_length:
            print(f"\nRunning brute-force attack (max length: {max_length})...")
            password = brute_force_attack(file_path, max_length)
    elif choice == '2':
        wordlist = simpledialog.askstring("Dictionary Attack", "Path to wordlist (e.g., rockyou.txt):")
        if wordlist:
            print("\nRunning dictionary attack...")
            password = dictionary_attack(file_path, wordlist)
    elif choice == '3':
        mask = simpledialog.askstring("Mask Attack", "Mask (e.g., ?u?l?l?d?d for 'Aaa11'):")
        if mask:
            print("\nRunning mask attack...")
            password = mask_attack(file_path, mask)
    else:
        print("Invalid choice.")

    if password:
        print(f"\nSuccess! Password: {password}")
    else:
        print("\nFailed to crack the password.")

if __name__ == "__main__":
    main()

import PyPDF2
import itertools
import string
from tkinter import filedialog, Tk, simpledialog
from tqdm import tqdm  # Import tqdm for the progress bar

def unlock_pdf(pdf_path, max_length):
    # Define the character set for the password
    chars = string.ascii_letters + string.digits + string.punctuation

    # Calculate the total number of possible passwords to try
    total_attempts = sum(len(chars) ** length for length in range(1, max_length + 1))

    # Initialize the progress bar
    progress_bar = tqdm(total=total_attempts, desc="Trying passwords", unit="attempt")

    # Try passwords of increasing length up to max_length
    for length in range(1, max_length + 1):
        for attempt in itertools.product(chars, repeat=length):
            password = ''.join(attempt)
            try:
                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    if pdf_reader.is_encrypted:
                        if pdf_reader.decrypt(password):
                            progress_bar.close()
                            print(f"Password found: {password}")
                            return password
            except Exception as e:
                print(f"Error trying password {password}: {e}")
            finally:
                progress_bar.update(1)  # Update the progress bar after each attempt

    progress_bar.close()
    return None

def pdf_to_text(pdf_path, password=None):
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            if pdf_reader.is_encrypted and password:
                pdf_reader.decrypt(password)
            
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            
            # Save the text to a file
            txt_path = pdf_path.replace('.pdf', '.txt')
            with open(txt_path, 'w', encoding='utf-8') as txt_file:
                txt_file.write(text)
            print(f"Text saved to {txt_path}")
    except Exception as e:
        print(f"Error converting PDF to text: {e}")

def main():
    # Let the user select the PDF file
    root = Tk()
    root.withdraw()
    pdf_path = filedialog.askopenfilename(title="Select the PDF file", filetypes=[("PDF files", "*.pdf")])
    if not pdf_path:
        print("No file selected.")
        return

    # Prompt the user for the maximum password length
    max_length = simpledialog.askinteger("Password Length", "Enter the maximum length of the password to try:", parent=root, minvalue=1, maxvalue=10)
    if not max_length:
        print("No password length provided.")
        return

    # Try to unlock the PDF
    password = unlock_pdf(pdf_path, max_length)
    if password:
        print(f"PDF unlocked successfully. Password: {password}")
        # Convert the PDF to text
        pdf_to_text(pdf_path, password)
    else:
        print("Failed to unlock the PDF.")

if __name__ == "__main__":
    main()

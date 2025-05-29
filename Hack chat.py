from pyfiglet import Figlet
GREEN = "\033[32;1m"
CYAN = "\033[36;1m"
RESET = "\033[0m"

def banner():
    print(GREEN)
    print("+" + "="*66 + "+")
    f= Figlet(font='block')
    print(f.renderText('CodeCr4cker'))
    print("+" + "="*66 + "+")
    print(RESET)

# Simulated client session output
banner()
print(CYAN + "Connected to darknet chat. Type /quit to exit." + RESET)
prompt = GREEN + "root@localhost:~# " + RESET
print()
print(prompt + "Hello there")  # Pretend this was user input
print("[12:00:01] Neo> Hello, world!")
print("[12:00:05] Trinity> We’re in.")

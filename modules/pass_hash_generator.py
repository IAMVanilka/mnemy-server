from passlib.hash import bcrypt
import secrets


def generate_password_hash(password):
    password_hash = bcrypt.hash(str(password))
    return password_hash


def generate_secret_key():
    secret_key = secrets.token_urlsafe(32)
    return secret_key


def run_generator():
    while True:
        print("Select an option:")
        print("1. Generate password hash")
        print("2. Generate secret key")


        choice = input("Enter your choice (1 or 2): ").strip()

        if choice == "1":
            password = input("Enter the password to hash: ")
            hashed = generate_password_hash(password)
            print(f"\nPassword hash: {hashed}")
            print("Use it in secrets.env > PANEL_PASSWORD\n")
            input('Press enter...\n')
        elif choice == "2":
            key = generate_secret_key()
            print(f"\nSecret key: {key}")
            print("Use it in secrets.env > SECRET_KEY\n")
            input('Press enter...\n')
        else:
            print("\nInvalid choice. Please enter 1 or 2.\n")

if __name__ == "__main__":
    run_generator()
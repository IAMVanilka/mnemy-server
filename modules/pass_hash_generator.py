from passlib.hash import bcrypt
import secrets

def generate_password_hash(password):
    password_hash = bcrypt.hash(str(password))
    return password_hash

def generate_secret_key():
    secret_key = secrets.token_urlsafe(32)
    return secret_key

print(generate_password_hash(123))
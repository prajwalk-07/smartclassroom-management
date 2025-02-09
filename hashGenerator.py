from werkzeug.security import generate_password_hash

# Generate password hash
password = "veda123"
hashed_password = generate_password_hash(password)
print(hashed_password)
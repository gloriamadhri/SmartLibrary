import secrets

secret_key = secrets.token_hex(16)  # Generate a 32-character hexadecimal string
print("Generated secret key:", secret_key)
#Generated secret key: d342e90b04ba20f98b309f4e432d13be
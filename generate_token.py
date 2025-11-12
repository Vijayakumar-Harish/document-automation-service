import datetime, jwt

secret = "KUHE(*kljdfljw30942lakd)"
algo = "HS256"
now = datetime.datetime.now(datetime.UTC)

payload = {
    "sub": "user1",
    "email": "harish@oneshot.com",
    "role": "user",
    "iat": now,
    "exp": now + datetime.timedelta(hours=8)
}

print(jwt.encode(payload, secret, algorithm=algo))

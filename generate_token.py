import jwt

print(jwt.encode({"sub":"user1", "email":"harish@oneshot.com", "role":"user"}, "KUHE(*kljdfljw30942lakd)", algorithm="HS256"))
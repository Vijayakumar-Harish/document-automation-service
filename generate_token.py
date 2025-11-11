import jwt

print(jwt.encode({"sub":"user1", "email":"bharath@oneshot.com", "role":"support"}, "KUHE(*kljdfljw30942lakd)", algorithm="HS256"))
from app import db, User

user_list = []
for i in range(60):
    user_list.append(User(f"temp_user{i}@test.com", f"Temp User{i}", "111", "0"))

db.session.add_all(user_list)
db.session.commit()
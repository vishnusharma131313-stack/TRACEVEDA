from database import db


users = [
    {
        "user_id": "LAB-001",
        "username": "Lab-001",
        "password": "123",
        "role": "laboratory"
    },
    {
        "user_id": "MFG-001",
        "username": "Man-001",
        "password": "123",
        "role": "manufacturer"
    },
    {
        "user_id": "CON-001",
        "username": "Con-001",
        "password": "123",
        "role": "consumer"
    },
    {
        "user_id": "AUD-001",
        "username": "Aud-001",
        "password": "123",
        "role": "auditor"
    }
]


for user in users:

    db.users.update_one(
        {"username": user["username"]},
        {"$set": user},
        upsert=True
    )

    print(
        f"Added/Updated: "
        f"{user['username']} "
        f"({user['role']})"
    )


print("\nUsers successfully added to MongoDB!")
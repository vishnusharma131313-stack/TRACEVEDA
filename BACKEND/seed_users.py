from services.accounts import create_user, set_password


users = [
    {
        "username": "lab-001",
        "password": "12345678",
        "role": "lab",
        "full_name": "Laboratory Demo"
    },
    {
        "username": "man-001",
        "password": "12345678",
        "role": "manufacturer",
        "full_name": "Manufacturer Demo"
    },
    {
        "username": "aud-001",
        "password": "12345678",
        "role": "regulator",
        "full_name": "Regulator Demo"
    },
    {
        "username": "admin-001",
        "password": "12345678",
        "role": "admin",
        "full_name": "TraceVeda Administrator",
        "organisation_id": "TRACEVEDA-HQ"
    },
]


for user in users:

    try:

        create_user(**user)

        print(f"Created: {user['username']}")

    except ValueError:

        set_password(
            user["username"],
            user["password"]
        )

        print(f"Password updated: {user['username']}")


print("\nUsers are ready!")
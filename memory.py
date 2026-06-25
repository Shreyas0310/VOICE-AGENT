import os
import json

MEMORY_FOLDER = "customer_memory"

os.makedirs(MEMORY_FOLDER, exist_ok=True)


def load_customer_history(phone_number: str):
    filename = os.path.join(
        MEMORY_FOLDER,
        f"{phone_number}.json"
    )

    if not os.path.exists(filename):
        return []

    with open(filename, "r") as file:
        return json.load(file)


def save_customer_history(phone_number: str, history):
    filename = os.path.join(
        MEMORY_FOLDER,
        f"{phone_number}.json"
    )

    with open(filename, "w") as file:
        json.dump(history, file, indent=4)


history = [
    {"role": "user", "content": "My name is Shreyas"},
    {"role": "assistant", "content": "Nice to meet you"}
]

save_customer_history("+917045596878", history)

print(load_customer_history("+917045596878"))


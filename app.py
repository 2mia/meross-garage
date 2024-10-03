from flask import Flask, request, jsonify
import json, logging
from datetime import datetime
import asyncio
import os

from meross_iot.http_api import MerossHttpClient
from meross_iot.manager import MerossManager
from meross_iot.controller.mixins.garage import GarageOpenerMixin

app = Flask(__name__)


EMAIL = os.environ.get('MEROSS_EMAIL')

# https://github.com/albertogeniola/MerossIot/blob/58de4e0594aa2a471c0c50b7230ceaca72b596d6/examples/cover.py#L4

# Configure logging with timestamps
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

@app.route('/')
def home():
    return "Hello! I am alive!"

async def get_doors(password):
    # Initialize the Meross HTTP client asynchronously
    http_api_client = await MerossHttpClient.async_from_user_password(
        api_base_url='https://iotx-us.meross.com',
        email=EMAIL,
        password=password
    )

    # Initialize the Meross manager
    manager = MerossManager(http_client=http_api_client)
    await manager.async_init()

    # Discover all devices
    await manager.async_device_discovery()

    # Retrieve all the devices that implement the garage-door opening mixin
    doors = manager.find_devices(device_class=GarageOpenerMixin, device_type="msg100")

    return doors

async def do_press_button(door):
    # Call async_update() on the door to refresh its state
    await door.async_update()

    if door.get_is_open():
        print(f"Door {door.name} is open. Sending close")
        await door.async_close()
    else:
        print(f"Door {door.name} is closed. Sending open")
        await door.async_open()

    await door.async_update()

    # After updating, get the current state of the door
    return door.get_is_open()

async def do_open_half(door, sleep_seconds):
    # Call async_update() on the door to refresh its state
    await door.async_update()

    if door.get_is_open():
        print(f"Door {door.name} is open. Doing nothing")
        return False
    
    print(f"Door {door.name} is closed. Sending open")
    await door.async_open()
    print(f"Waiting {sleep_seconds} seconds before closing")
    await asyncio.sleep(sleep_seconds)
    await door.async_close()

    await door.async_update()
    # After updating, get the current state of the door
    return door.get_is_open()


def get_password():
    data = request.get_json()

    # Ensure the password is provided in the JSON body
    if not data or 'password' not in data:
        return jsonify({"error": "Password is required"}), 400

    return data['password']

@app.route("/toggle", methods=["POST"])
def toggle():
    password = get_password()
    print(f"Received password: {password}")
    # Create an event loop or reuse the existing one
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Run the async function to get the devices in the same event loop
    doors = loop.run_until_complete(get_doors(password))

    if doors:
        door = doors[0]
        
        logging.info("Methods of the first device:")
        logging.info(dir(door))  # Print all methods of the door

        # Run async_update and get the state in the same event loop
        door_state = loop.run_until_complete(do_press_button(door))

    # Convert the devices to JSON-friendly format (e.g., using str())
    doors_serializable = [str(door) for door in doors]

    # Return the filtered devices as a JSON response
    return jsonify(doors_serializable)

@app.route("/open-half", methods=["POST"])
def open_close(seconds):
    password = get_password()
    # Create an event loop or reuse the existing one
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Run the async function to get the devices in the same event loop
    doors = loop.run_until_complete(get_doors(password))

    if doors:
        door = doors[0]
        door_state = loop.run_until_complete(do_open_half(door, seconds))

    # Convert the devices to JSON-friendly format (e.g., using str())
    doors_serializable = [str(door) for door in doors]

    # Return the filtered devices as a JSON response
    return jsonify(doors_serializable)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

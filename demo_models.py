#!/usr/bin/env python3
"""
Database Model Demo Script for Sprint Review
Demonstrates core functionality and design highlights of database models
"""

import requests

# API Base URL
BASE_URL = "http://127.0.0.1:8080"


def demo_database_models():
    """Demonstrate core functionality of database models"""
    print("🎯 Database Model Demo - Sprint Review")
    print("=" * 50)

    # 1. Test Service Status
    print("\n1. Checking service status...")
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print("✅ Service is running normally")
            print(f"   Service Info: {response.json()}")
        else:
            print("❌ Service is not responding")
            return
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    # 2. Create Shopcart - Demonstrate Shopcart Model
    print("\n2. Creating shopcart (Shopcart Model)...")
    shopcart_data = {
        "customer_id": 12345,
        "status": "active",
        "total_items": 0
    }

    try:
        response = requests.post(
            f"{BASE_URL}/shopcarts",
            json=shopcart_data,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 201:
            shopcart = response.json()
            print("✅ Shopcart created successfully")
            print(f"   Shopcart ID: {shopcart['id']}")
            print(f"   Customer ID: {shopcart['customer_id']}")
            print(f"   Status: {shopcart['status']}")
            print(f"   Created Date: {shopcart['created_date']}")
        else:
            print(f"❌ Creation failed: {response.status_code} - {response.text}")
            return

    except Exception as e:
        print(f"❌ Failed to create shopcart: {e}")
        return

    # 3. Add Items - Demonstrate ShopcartItem Model
    print("\n3. Adding items to shopcart (ShopcartItem Model)...")

    items_to_add = [
        {
            "product_id": 1001,
            "quantity": 2,
            "price": 19.99,
            "description": "NYU T-Shirt"
        },
        {
            "product_id": 1002,
            "quantity": 1,
            "price": 49.99,
            "description": "NYU Hoodie"
        },
        {
            "product_id": 1003,
            "quantity": 3,
            "price": 9.99,
            "description": "NYU Mug"
        }
    ]

    for i, item in enumerate(items_to_add, 1):
        try:
            response = requests.post(
                f"{BASE_URL}/shopcarts/12345/items",
                json=item,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 201:
                created_item = response.json()
                print(f"✅ Item {i} added successfully")
                print(f"   Item ID: {created_item['id']}")
                print(f"   Product ID: {created_item['product_id']}")
                print(f"   Quantity: {created_item['quantity']}")
                print(f"   Price: ${created_item['price']}")
                print(f"   Description: {created_item['description']}")
            else:
                print(f"❌ Failed to add item {i}: {response.status_code} - {response.text}")

        except Exception as e:
            print(f"❌ Failed to add item {i}: {e}")

    # 4. View Complete Shopcart - Demonstrate Relationship Mapping
    print("\n4. Viewing complete shopcart (Relationship Mapping)...")
    try:
        response = requests.get(
            f"{BASE_URL}/shopcarts/12345",
            headers={"X-Customer-ID": "12345"}
        )

        if response.status_code == 200:
            shopcart = response.json()
            print("✅ Shopcart details retrieved successfully")
            print(f"   Shopcart ID: {shopcart['id']}")
            print(f"   Customer ID: {shopcart['customer_id']}")
            print(f"   Status: {shopcart['status']}")
            print(f"   Total Items: {shopcart['total_items']}")
            print(f"   Last Modified: {shopcart['last_modified']}")
            print("   Item List:")

            for item in shopcart['items']:
                print(f"     - {item['description']} (ID: {item['product_id']})")
                print(f"       Quantity: {item['quantity']}, Price: ${item['price']}")
        else:
            print(f"❌ Failed to retrieve shopcart: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"❌ Failed to retrieve shopcart: {e}")

    # 5. Update Item Quantity - Demonstrate Upsert Functionality
    print("\n5. Updating item quantity (Upsert Functionality)...")
    try:
        update_data = {
            "quantity": 5,
            "price": 19.99,
            "description": "NYU T-Shirt (Updated)"
        }

        response = requests.patch(
            f"{BASE_URL}/shopcarts/12345/items/1001",
            json=update_data,
            headers={"X-Customer-ID": "12345"}
        )

        if response.status_code == 200:
            updated_item = response.json()
            print("✅ Item updated successfully")
            print(f"   New Quantity: {updated_item['quantity']}")
            print(f"   New Description: {updated_item['description']}")
        else:
            print(f"❌ Failed to update item: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"❌ Failed to update item: {e}")

    # 6. Delete Item - Demonstrate Delete Functionality
    print("\n6. Deleting item (Delete Functionality)...")
    try:
        response = requests.delete(f"{BASE_URL}/shopcarts/12345/items/1003")

        if response.status_code == 204:
            print("✅ Item deleted successfully")
        else:
            print(f"❌ Failed to delete item: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"❌ Failed to delete item: {e}")

    # 7. Final Shopcart Status
    print("\n7. Final shopcart status...")
    try:
        response = requests.get(
            f"{BASE_URL}/shopcarts/12345",
            headers={"X-Customer-ID": "12345"}
        )

        if response.status_code == 200:
            shopcart = response.json()
            print("✅ Final Status:")
            print(f"   Total Items: {shopcart['total_items']}")
            print(f"   Item Count: {len(shopcart['items'])}")
            for item in shopcart['items']:
                print(f"     - {item['description']}: {item['quantity']} x ${item['price']}")
        else:
            print(f"❌ Failed to retrieve final status: {response.status_code}")

    except Exception as e:
        print(f"❌ Failed to retrieve final status: {e}")

    print("\n" + "=" * 50)
    print("🎉 Database Model Demo Completed!")
    print("\nTechnical Highlights Summary:")
    print("✅ Shopcart Model - Shopcart Management")
    print("✅ ShopcartItem Model - Item Management")
    print("✅ Relationship Mapping - One-to-Many Relationship")
    print("✅ Data Validation - Complete Error Handling")
    print("✅ Serialization/Deserialization - JSON Conversion")
    print("✅ CRUD Operations - Create, Read, Update, Delete")
    print("✅ Business Logic - Smart Upsert Functionality")


if __name__ == "__main__":
    demo_database_models()

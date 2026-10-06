import sqlite3
import random
import os
from werkzeug.security import generate_password_hash

CATEGORIES = ['electronics', 'clothing', 'books', 'food', 'sports']
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database.sqlite')

def seed_database():
    print(f"Connecting to database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        print("Clearing old data...")
        cur.execute("DELETE FROM orders;")
        cur.execute("DELETE FROM products;")
        cur.execute("DELETE FROM users;")
        
        print("Seeding users...")
        user_ids = []
        for i in range(50):
            username = f"user_{i+1}"
            email = f"user_{i+1}@example.com"
            pw_hash = generate_password_hash("pass123")
            cur.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, pw_hash)
            )
            user_ids.append(cur.lastrowid)
        
        print("Seeding products...")
        product_ids = []
        for i in range(100):
            name = f"Product {i+1}"
            desc = f"A great product in category {random.choice(CATEGORIES)}"
            price = round(random.uniform(5.0, 500.0), 2)
            category = random.choice(CATEGORIES)
            cur.execute(
                "INSERT INTO products (name, description, price, category) VALUES (?, ?, ?, ?)",
                (name, desc, price, category)
            )
            product_ids.append(cur.lastrowid)

        print("Seeding orders...")
        for i in range(200):
            user_id = random.choice(user_ids)
            product_id = random.choice(product_ids)
            quantity = random.randint(1, 5)
            # Fetch product price to calculate total
            cur.execute("SELECT price FROM products WHERE id = ?", (product_id,))
            price = cur.fetchone()[0]
            total_price = price * quantity
            status = random.choice(['pending', 'completed', 'shipped', 'cancelled'])
            cur.execute(
                "INSERT INTO orders (user_id, product_id, quantity, total_price, status) VALUES (?, ?, ?, ?, ?)",
                (user_id, product_id, quantity, total_price, status)
            )

        conn.commit()
        print("Seeding completed successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Error during seeding: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    seed_database()

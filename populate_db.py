import random
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from app.config import get_settings

settings = get_settings()

DB_URI = settings.database_url


def populate_database():
    engine = create_engine(DB_URI)

    with engine.connect() as conn:
        # 1. Clear existing data (Clean slate)
        print("Clearing old data...")
        conn.execute(text("DROP TABLE IF EXISTS orders;"))
        conn.execute(text("DROP TABLE IF EXISTS products;"))
        conn.execute(text("DROP TABLE IF EXISTS customers;"))
        conn.commit()

        # 2. Create Schema
        print("Creating schema...")
        conn.execute(
            text(
                """
            CREATE TABLE customers (
                customer_id SERIAL PRIMARY KEY,
                name VARCHAR(100),
                email VARCHAR(100),
                city VARCHAR(50),
                signup_date DATE
            );
        """
            )
        )

        conn.execute(
            text(
                """
            CREATE TABLE products (
                product_id SERIAL PRIMARY KEY,
                product_name VARCHAR(100),
                category VARCHAR(50),
                price DECIMAL(10, 2)
            );
        """
            )
        )

        conn.execute(
            text(
                """
            CREATE TABLE orders (
                order_id SERIAL PRIMARY KEY,
                customer_id INTEGER REFERENCES customers(customer_id),
                product_id INTEGER REFERENCES products(product_id),
                order_date DATE,
                quantity INTEGER,
                total_amount DECIMAL(10, 2),
                status VARCHAR(20) -- e.g., 'completed', 'returned', 'pending'
            );
        """
            )
        )
        conn.commit()

        # 3. Generate Dummy Data
        print("Generating customers...")
        cities = [
            "New York",
            "Los Angeles",
            "Chicago",
            "Houston",
            "Phoenix",
            "London",
            "Berlin",
        ]
        customers = []
        for i in range(1, 101):  # 100 Customers
            name = f"User_{i}"
            email = f"user_{i}@email.com"
            city = random.choice(cities)
            signup = datetime.now() - timedelta(days=random.randint(100, 1000))
            customers.append(
                f"('{name}', '{email}', '{city}', '{signup.strftime('%Y-%m-%d')}')"
            )

        conn.execute(
            text(
                f"INSERT INTO customers (name, email, city, signup_date) VALUES {','.join(customers)}"
            )
        )
        conn.commit()

        print("Generating products...")
        categories = ["Electronics", "Books", "Clothing", "Home & Kitchen", "Sports"]
        products = []
        for i in range(1, 51):  # 50 Products
            name = f"Product_{i}"
            cat = random.choice(categories)
            price = round(random.uniform(10, 500), 2)
            products.append(f"('{name}', '{cat}', {price})")

        conn.execute(
            text(
                f"INSERT INTO products (product_name, category, price) VALUES {','.join(products)}"
            )
        )
        conn.commit()

        print("Generating orders (this may take a moment)...")
        statuses = ["completed", "completed", "completed", "returned", "pending"]

        # Batch insert for speed
        batch_size = 1000
        total_orders = 5000  # 5000 orders for extensive testing

        for batch_start in range(0, total_orders, batch_size):
            orders = []
            for _ in range(batch_start, min(batch_start + batch_size, total_orders)):
                cust_id = random.randint(1, 100)
                prod_id = random.randint(1, 50)
                qty = random.randint(1, 5)
                amount = round(qty * random.uniform(10, 100), 2)
                date = datetime.now() - timedelta(days=random.randint(1, 365))
                status = random.choice(statuses)
                orders.append(
                    f"({cust_id}, {prod_id}, '{date.strftime('%Y-%m-%d')}', {qty}, {amount}, '{status}')"
                )

            conn.execute(
                text(
                    f"INSERT INTO orders (customer_id, product_id, order_date, quantity, total_amount, status) VALUES {','.join(orders)}"
                )
            )
            conn.commit()

        print("✅ Database populated successfully!")
        print("Tables: customers (100 rows), products (50 rows), orders (5000 rows)")


if __name__ == "__main__":
    populate_database()

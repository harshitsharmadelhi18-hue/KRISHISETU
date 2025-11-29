#GRAIN GARDIANS B-TECH CSE 1ST YEAR PYTHON FINAL PROJECT
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkfont
import re
import mysql.connector
from mysql.connector import Error
from contextlib import contextmanager

# ------------------ DB CONFIG - EDIT THESE ------------------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",            # <- change to your DB user
    "password": "1234",   # <- change to your DB password
    "port": 3306
}
DB_NAME = "k"
# ------------------------------------------------------------

# ---------- Product catalog for consumers (static) ----------
PRODUCT_CATALOG = [
    {"name": "Rice", "price": 100.0},
    {"name": "Wheat", "price": 80.0},
    {"name": "Black Pepper", "price": 120.0},
    {"name": "Cotton", "price": 200.0},
    {"name": "Cereals", "price": 150.0},
]


# ---------- Helpers ----------
def is_valid_email(email: str) -> bool:
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))


def is_valid_phone(phone: str) -> bool:
    return bool(re.match(r"^\d{7,15}$", phone))


# ---------- DB utilities ----------
def _connect_without_db():
    """Connect to MySQL server without selecting a database (used for initial DB creation)."""
    return mysql.connector.connect(
        host=DB_CONFIG["host"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        port=DB_CONFIG.get("port", 3306),
        autocommit=True
    )


@contextmanager
def get_connection():
    """Context manager that connects to the application database (creates if missing)."""
    conn = None
    try:
        conn = mysql.connector.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_NAME,
            port=DB_CONFIG.get("port", 3306),
            autocommit=False
        )
        yield conn
    except Error as e:
        print("DB error:", e)
        raise
    finally:
        if conn and conn.is_connected():
            conn.close()


def init_db():
    """Create database and tables if they don't exist."""
    create_db_sql = f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    create_tables_sql = [
        # farmers
        """
        CREATE TABLE IF NOT EXISTS farmers (
          id INT AUTO_INCREMENT PRIMARY KEY,
          name VARCHAR(150) NOT NULL,
          email VARCHAR(255) NOT NULL UNIQUE,
          phone VARCHAR(20) NOT NULL,
          location VARCHAR(255),
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB;
        """,
        # farmer_crops
        """
        CREATE TABLE IF NOT EXISTS farmer_crops (
          id INT AUTO_INCREMENT PRIMARY KEY,
          farmer_id INT NOT NULL,
          crop_name VARCHAR(150) NOT NULL,
          price_per_kg DECIMAL(10,2) NOT NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT fk_farmer FOREIGN KEY (farmer_id) REFERENCES farmers(id) ON DELETE CASCADE ON UPDATE CASCADE
        ) ENGINE=InnoDB;
        """,
        # consumers
        """
        CREATE TABLE IF NOT EXISTS consumers (
          id INT AUTO_INCREMENT PRIMARY KEY,
          name VARCHAR(150) NOT NULL,
          email VARCHAR(255) NOT NULL UNIQUE,
          phone VARCHAR(20) NOT NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB;
        """,
        # cart_items
        """
        CREATE TABLE IF NOT EXISTS cart_items (
          id INT AUTO_INCREMENT PRIMARY KEY,
          consumer_id INT NOT NULL,
          product_name VARCHAR(150) NOT NULL,
          price_per_kg DECIMAL(10,2) NOT NULL,
          qty INT NOT NULL DEFAULT 1,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT fk_consumer FOREIGN KEY (consumer_id) REFERENCES consumers(id) ON DELETE CASCADE ON UPDATE CASCADE
        ) ENGINE=InnoDB;
        """
    ]

    # create db if needed
    conn0 = None
    try:
        conn0 = _connect_without_db()
        cur0 = conn0.cursor()
        cur0.execute(create_db_sql)
        cur0.close()
        conn0.close()
    except Error as e:
        if conn0 and conn0.is_connected():
            conn0.close()
        raise

    # create tables inside the new DB
    with get_connection() as conn:
        cur = conn.cursor()
        for sql in create_tables_sql:
            cur.execute(sql)
        conn.commit()
        cur.close()


# ---------- DB operations ----------
def insert_farmer_with_crops(name, email, phone, location, crops):
    """
    Insert farmer and crops. crops: list of {'crop': name, 'price': float}
    Returns inserted farmer_id.
    """
    with get_connection() as conn:
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO farmers (name, email, phone, location) VALUES (%s,%s,%s,%s)",
                (name, email, phone, location)
            )
            farmer_id = cur.lastrowid
            for c in crops:
                cur.execute(
                    "INSERT INTO farmer_crops (farmer_id, crop_name, price_per_kg) VALUES (%s,%s,%s)",
                    (farmer_id, c["crop"], float(c["price"]))
                )
            conn.commit()
            cur.close()
            return farmer_id
        except Exception:
            conn.rollback()
            raise


def fetch_all_farmers_with_crops():
    sql = """
    SELECT f.id AS farmer_id, f.name AS farmer_name, f.email, f.phone, f.location,
           fc.id AS crop_id, fc.crop_name, fc.price_per_kg
    FROM farmers f
    LEFT JOIN farmer_crops fc ON fc.farmer_id = f.id
    ORDER BY f.id, fc.crop_name;
    """
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql)
        rows = cur.fetchall()
        cur.close()
    farmers = {}
    for r in rows:
        fid = r["farmer_id"]
        if fid not in farmers:
            farmers[fid] = {
                "id": fid,
                "name": r["farmer_name"],
                "email": r["email"],
                "phone": r["phone"],
                "location": r["location"],
                "crops": []
            }
        if r["crop_id"] is not None:
            farmers[fid]["crops"].append({
                "crop_id": r["crop_id"],
                "crop_name": r["crop_name"],
                "price_per_kg": float(r["price_per_kg"])
            })
    return list(farmers.values())


def find_or_create_consumer(name, email, phone):
    """
    Returns consumer_id for the given email (create if not exists).
    """
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        # try fetch by email
        cur.execute("SELECT id FROM consumers WHERE email = %s", (email,))
        row = cur.fetchone()
        if row:
            cid = row["id"]
            cur.close()
            return cid
        # else insert
        cur.execute("INSERT INTO consumers (name, email, phone) VALUES (%s,%s,%s)", (name, email, phone))
        cid = cur.lastrowid
        conn.commit()
        cur.close()
        return cid


def add_or_update_cart_item(consumer_id, product_name, price_per_kg, qty):
    """
    If item with same product_name exists for consumer, increase qty, else insert.
    """
    with get_connection() as conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT id, qty FROM cart_items
                WHERE consumer_id = %s AND product_name = %s AND price_per_kg = %s
            """, (consumer_id, product_name, price_per_kg))
            row = cur.fetchone()
            if row:
                new_qty = int(row["qty"]) + int(qty)
                cur.execute("UPDATE cart_items SET qty = %s WHERE id = %s", (new_qty, row["id"]))
            else:
                cur.execute(
                    "INSERT INTO cart_items (consumer_id, product_name, price_per_kg, qty) VALUES (%s,%s,%s,%s)",
                    (consumer_id, product_name, price_per_kg, qty)
                )
            conn.commit()
            cur.close()
        except Exception:
            conn.rollback()
            raise


def fetch_cart_for_consumer(consumer_id):
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT id AS cart_id, product_name, price_per_kg, qty FROM cart_items
            WHERE consumer_id = %s ORDER BY created_at;
        """, (consumer_id,))
        rows = cur.fetchall()
        cur.close()
    return rows


def remove_cart_item(cart_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM cart_items WHERE id = %s", (cart_id,))
        conn.commit()
        cur.close()


def clear_cart_for_consumer(consumer_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM cart_items WHERE consumer_id = %s", (consumer_id,))
        conn.commit()
        cur.close()


# ----------------- Tkinter Application -----------------
class CropPortalApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Crops Portal (MySQL)")
        self.geometry("980x640")
        self.minsize(900, 600)
        self.configure(bg="#f3f6fb")

        # runtime variables
        self.consumer_id = None
        self.consumer_name = None

        # style
        self.header_font = tkfont.Font(family="Segoe UI", size=18, weight="bold")
        self.sub_font = tkfont.Font(family="Segoe UI", size=11)
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TFrame", background="#f3f6fb")
        self.style.configure("Card.TFrame", background="#ffffff", relief="flat")
        self.style.configure("Accent.TButton", foreground="white", background="#0b71ea", padding=8)
        self.style.map("Accent.TButton",
                       background=[("active", "#075fcc"), ("disabled", "#9bbcf7")])
        self.style.configure("TButton", padding=6)
        self.style.configure("TLabel", background="#f3f6fb")
        self.style.configure("Title.TLabel", font=self.header_font, background="#f3f6fb")
        self.style.configure("Small.TLabel", font=self.sub_font, background="#f3f6fb")

        container = ttk.Frame(self, style="TFrame")
        container.pack(fill="both", expand=True, padx=20, pady=18)

        title_frame = ttk.Frame(container, style="TFrame")
        title_frame.pack(fill="x", pady=(0, 12))
        ttk.Label(title_frame, text="Crops Portal", style="Title.TLabel").pack(side="left")
        ttk.Label(title_frame, text="Buy & Sell with farmers (DB-backed)", style="Small.TLabel").pack(side="left", padx=12)

        self.main_frame = ttk.Frame(container, style="TFrame")
        self.main_frame.pack(fill="both", expand=True)

        # initialize DB (create tables if needed)
        try:
            init_db()
        except Exception as e:
            messagebox.showerror("DB Error", f"Failed to initialize database: {e}")
            self.destroy()
            return

        self.show_home()

    def clear_main(self):
        for w in self.main_frame.winfo_children():
            w.destroy()

    def show_home(self):
        self.clear_main()
        frame = ttk.Frame(self.main_frame, style="TFrame")
        frame.pack(expand=True, pady=40)

        card = ttk.Frame(frame, style="Card.TFrame")
        card.pack(ipadx=30, ipady=18, padx=10, pady=10)

        ttk.Label(card, text="Who are you?", font=self.header_font, background="#ffffff").pack(pady=(6, 14))

        btn_frame = ttk.Frame(card, style="Card.TFrame")
        btn_frame.pack(pady=8, padx=18)

        farmer_btn = ttk.Button(btn_frame, text="Farmer", style="Accent.TButton", command=self.show_farmer_portal)
        consumer_btn = ttk.Button(btn_frame, text="Consumer", style="Accent.TButton", command=self.show_consumer_login)

        farmer_btn.grid(row=0, column=0, padx=12, ipadx=8)
        consumer_btn.grid(row=0, column=1, padx=12, ipadx=8)

        stats = ttk.Frame(card, style="Card.TFrame")
        stats.pack(pady=(18, 4), fill="x", padx=12)
        farmers = fetch_all_farmers_with_crops()
        cart_count = 0
        if self.consumer_id:
            cart_items = fetch_cart_for_consumer(self.consumer_id)
            cart_count = sum(int(it["qty"]) for it in cart_items)
        stats_label = ttk.Label(stats, text=f"Registered farmers: {len(farmers)}    Cart items: {cart_count}", background="#ffffff")
        stats_label.pack()

    # ---------- Farmer portal ----------
    def show_farmer_portal(self):
        self.clear_main()
        frame = ttk.Frame(self.main_frame, style="TFrame")
        frame.pack(fill="both", expand=True, padx=12, pady=8)

        # left: registration
        left = ttk.Frame(frame, style="Card.TFrame")
        left.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        ttk.Label(left, text="Farmer Registration", font=self.header_font, background="#ffffff").pack(pady=(8, 12))

        form = ttk.Frame(left, style="Card.TFrame")
        form.pack(padx=12, pady=6, fill="x")

        self.f_name = tk.StringVar()
        self.f_email = tk.StringVar()
        self.f_phone = tk.StringVar()
        self.f_location = tk.StringVar()
        ttk.Label(form, text="Full name").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.f_name).grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        ttk.Label(form, text="Email").grid(row=1, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.f_email).grid(row=1, column=1, sticky="ew", padx=6, pady=4)
        ttk.Label(form, text="Phone").grid(row=2, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.f_phone).grid(row=2, column=1, sticky="ew", padx=6, pady=4)
        ttk.Label(form, text="Location").grid(row=3, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.f_location).grid(row=3, column=1, sticky="ew", padx=6, pady=4)
        form.columnconfigure(1, weight=1)

        ttk.Separator(left).pack(fill="x", pady=8)
        ttk.Label(left, text="Add Crops", font=self.sub_font, background="#ffffff").pack(anchor="w", padx=12)
        crop_area = ttk.Frame(left, style="Card.TFrame")
        crop_area.pack(fill="x", padx=12, pady=(6, 12))

        self.crop_name_var = tk.StringVar()
        self.crop_price_var = tk.StringVar()
        ttk.Label(crop_area, text="Crop name").grid(row=0, column=0, sticky="w")
        ttk.Entry(crop_area, textvariable=self.crop_name_var).grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        ttk.Label(crop_area, text="Price per kg (₹)").grid(row=1, column=0, sticky="w")
        ttk.Entry(crop_area, textvariable=self.crop_price_var).grid(row=1, column=1, sticky="ew", padx=6, pady=4)
        add_crop_btn = ttk.Button(crop_area, text="Add Crop to List", command=self._add_crop_to_temp_list)
        add_crop_btn.grid(row=2, column=0, columnspan=2, pady=8)
        crop_area.columnconfigure(1, weight=1)

        ttk.Label(left, text="Crops to register:", background="#ffffff").pack(anchor="w", padx=12)
        self.temp_crops = []
        self.crops_listbox = tk.Listbox(left, height=6)
        self.crops_listbox.pack(fill="x", padx=12, pady=(6, 6))

        register_btn = ttk.Button(left, text="Register Farmer (save to DB)", style="Accent.TButton", command=self._register_farmer_db)
        register_btn.pack(pady=(8, 14))

        # right: view farmers from DB
        right = ttk.Frame(frame, style="Card.TFrame")
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        ttk.Label(right, text="Registered Farmers (from DB)", font=self.header_font, background="#ffffff").pack(pady=(8, 10))
        self.farmers_tree = ttk.Treeview(right, columns=("id", "name", "email", "phone", "location", "crops"), show="headings", height=12)
        self.farmers_tree.heading("id", text="ID")
        self.farmers_tree.heading("name", text="Name")
        self.farmers_tree.heading("email", text="Email")
        self.farmers_tree.heading("phone", text="Phone")
        self.farmers_tree.heading("location", text="Location")
        self.farmers_tree.heading("crops", text="Crops (name:₹kg)")
        self.farmers_tree.pack(fill="both", padx=12, pady=(4, 8))
        ttk.Button(right, text="Refresh", command=self._refresh_farmers_from_db).pack(side="left", padx=8, pady=6)
        ttk.Button(right, text="Back", command=self.show_home).pack(side="left", padx=8, pady=6)

        self._refresh_farmers_from_db()

    def _add_crop_to_temp_list(self):
        name = self.crop_name_var.get().strip()
        price = self.crop_price_var.get().strip()
        if not name:
            messagebox.showwarning("Missing", "Please enter crop name.")
            return
        try:
            price_val = float(price)
            if price_val <= 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Invalid", "Enter a valid positive price (rupees per kg).")
            return
        self.temp_crops.append({"crop": name, "price": price_val})
        self.crops_listbox.insert("end", f"{name} : ₹{price_val:.2f}/kg")
        self.crop_name_var.set("")
        self.crop_price_var.set("")

    def _register_farmer_db(self):
        name = self.f_name.get().strip()
        email = self.f_email.get().strip()
        phone = self.f_phone.get().strip()
        location = self.f_location.get().strip()
        if not (name and email and phone and location):
            messagebox.showwarning("Missing", "Fill all farmer details.")
            return
        if not is_valid_email(email):
            messagebox.showwarning("Invalid", "Enter a valid email.")
            return
        if not is_valid_phone(phone):
            messagebox.showwarning("Invalid", "Enter a valid phone.")
            return
        if not self.temp_crops:
            messagebox.showwarning("No crops", "Add at least one crop.")
            return
        try:
            farmer_id = insert_farmer_with_crops(name, email, phone, location, self.temp_crops)
            messagebox.showinfo("Success", f"Farmer registered in DB with id {farmer_id}.")
            # reset UI
            self.f_name.set("")
            self.f_email.set("")
            self.f_phone.set("")
            self.f_location.set("")
            self.crops_listbox.delete(0, "end")
            self.temp_crops.clear()
            self._refresh_farmers_from_db()
        except mysql.connector.IntegrityError as ie:
            messagebox.showerror("DB Error", f"Integrity error: {ie}")
        except Exception as e:
            messagebox.showerror("DB Error", f"Failed to register farmer: {e}")

    def _refresh_farmers_from_db(self):
        for row in self.farmers_tree.get_children():
            self.farmers_tree.delete(row)
        try:
            farmers = fetch_all_farmers_with_crops()
            for f in farmers:
                crops_str = "; ".join([f"{c['crop_name']} : ₹{float(c['price_per_kg']):.2f}/kg" for c in f["crops"]])
                self.farmers_tree.insert("", "end", values=(f["id"], f["name"], f["email"], f["phone"], f["location"], crops_str))
        except Exception as e:
            messagebox.showerror("DB Error", f"Failed to fetch farmers: {e}")

    # ---------- Consumer ----------
    def show_consumer_login(self):
        self.clear_main()
        frame = ttk.Frame(self.main_frame, style="TFrame")
        frame.pack(fill="both", expand=True, padx=24, pady=8)

        card = ttk.Frame(frame, style="Card.TFrame")
        card.pack(padx=12, pady=12, fill="both", expand=True)

        ttk.Label(card, text="Consumer Login", font=self.header_font, background="#ffffff").pack(pady=(8, 12))
        form = ttk.Frame(card, style="Card.TFrame")
        form.pack(padx=12, pady=6, fill="x")

        self.c_name = tk.StringVar()
        self.c_email = tk.StringVar()
        self.c_phone = tk.StringVar()

        ttk.Label(form, text="Full name").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.c_name).grid(row=0, column=1, sticky="ew", padx=6, pady=6)
        ttk.Label(form, text="Email").grid(row=1, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.c_email).grid(row=1, column=1, sticky="ew", padx=6, pady=6)
        ttk.Label(form, text="Phone").grid(row=2, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.c_phone).grid(row=2, column=1, sticky="ew", padx=6, pady=6)
        form.columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(card, style="Card.TFrame")
        btn_frame.pack(pady=8)
        ttk.Button(btn_frame, text="Login & Browse", style="Accent.TButton", command=self._consumer_login).grid()

        ttk.Button(card, text="Back", command=self.show_home).pack(side="left", padx=12, pady=8)

    def _consumer_login(self):
        name = self.c_name.get().strip()
        email = self.c_email.get().strip()
        phone = self.c_phone.get().strip()
        if not (name and email and phone):
            messagebox.showwarning("Missing", "Fill all login fields.")
            return
        if not is_valid_email(email):
            messagebox.showwarning("Invalid", "Enter a valid email.")
            return
        if not is_valid_phone(phone):
            messagebox.showwarning("Invalid", "Enter a valid phone.")
            return
        try:
            cid = find_or_create_consumer(name, email, phone)
            self.consumer_id = cid
            self.consumer_name = name
            self.show_product_list()
        except Exception as e:
            messagebox.showerror("DB Error", f"Failed to create/find consumer: {e}")

    def show_product_list(self):
        self.clear_main()
        frame = ttk.Frame(self.main_frame, style="TFrame")
        frame.pack(fill="both", expand=True, padx=12, pady=8)

        header = ttk.Frame(frame, style="TFrame")
        header.pack(fill="x", pady=(8, 6))
        ttk.Label(header, text=f"Welcome, {self.consumer_name}", font=self.header_font).pack(side="left")
        ttk.Button(header, text="View Cart", command=self.show_cart).pack(side="right", padx=6)
        ttk.Button(header, text="Logout", command=self._consumer_logout).pack(side="right", padx=6)

        products_frame = ttk.Frame(frame, style="TFrame")
        products_frame.pack(fill="both", expand=True, pady=12, padx=8)

        # create cards for products
        for idx, p in enumerate(PRODUCT_CATALOG):
            card = ttk.Frame(products_frame, style="Card.TFrame")
            card.grid(row=idx // 2, column=idx % 2, padx=10, pady=10, sticky="nsew")
            card.config(width=420, height=140)
            ttk.Label(card, text=p["name"], font=("Segoe UI", 14, "bold"), background="#ffffff").pack(anchor="w", padx=12, pady=(10, 4))
            ttk.Label(card, text=f"Price: ₹{p['price']:.2f} per kg", background="#ffffff").pack(anchor="w", padx=12)
            qty_frame = ttk.Frame(card, style="Card.TFrame")
            qty_frame.pack(anchor="w", padx=12, pady=8)
            ttk.Label(qty_frame, text="Qty (kg):", background="#ffffff").pack(side="left")
            qty_var = tk.IntVar(value=1)
            spin = tk.Spinbox(qty_frame, from_=1, to=1000, width=6, textvariable=qty_var)
            spin.pack(side="left", padx=(6, 12))
            add_btn = ttk.Button(qty_frame, text="Add to Cart",
                                 command=lambda prod=p, q=qty_var: self._add_product_to_cart_db(prod, q.get()))
            add_btn.pack(side="left")

        rows = (len(PRODUCT_CATALOG) + 1) // 2
        for r in range(rows):
            products_frame.rowconfigure(r, weight=1)
        products_frame.columnconfigure(0, weight=1)
        products_frame.columnconfigure(1, weight=1)

    def _add_product_to_cart_db(self, product, qty):
        try:
            qty = int(qty)
            if qty <= 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Invalid", "Enter a valid quantity.")
            return
        if not self.consumer_id:
            messagebox.showwarning("Not logged in", "Please login first.")
            return
        try:
            add_or_update_cart_item(self.consumer_id, product["name"], float(product["price"]), qty)
            messagebox.showinfo("Added", f"Added {qty} kg {product['name']} to cart (DB).")
        except Exception as e:
            messagebox.showerror("DB Error", f"Failed to add to cart: {e}")

    def _consumer_logout(self):
        self.consumer_id = None
        self.consumer_name = None
        self.show_home()

    # ---------- Cart ----------
    def show_cart(self):
        if not self.consumer_id:
            messagebox.showwarning("Not logged in", "Please login first.")
            return
        self.clear_main()
        frame = ttk.Frame(self.main_frame, style="TFrame")
        frame.pack(fill="both", expand=True, padx=12, pady=8)

        header = ttk.Frame(frame, style="TFrame")
        header.pack(fill="x", pady=(8, 6))
        ttk.Label(header, text="Your Cart", font=self.header_font).pack(side="left")
        ttk.Button(header, text="Back to Products", command=self.show_product_list).pack(side="right", padx=6)
        ttk.Button(header, text="Home", command=self.show_home).pack(side="right", padx=6)

        cart_frame = ttk.Frame(frame, style="Card.TFrame")
        cart_frame.pack(fill="both", expand=True, padx=12, pady=12)

        columns = ("cart_id", "product", "price", "qty", "subtotal")
        tree = ttk.Treeview(cart_frame, columns=columns, show="headings", height=12)
        tree.heading("cart_id", text="Cart ID")
        tree.heading("product", text="Product")
        tree.heading("price", text="Price/kg (₹)")
        tree.heading("qty", text="Qty (kg)")
        tree.heading("subtotal", text="Subtotal (₹)")
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        try:
            items = fetch_cart_for_consumer(self.consumer_id)
        except Exception as e:
            messagebox.showerror("DB Error", f"Failed to fetch cart items: {e}")
            return

        total = 0.0
        for it in items:
            subtotal = float(it["price_per_kg"]) * int(it["qty"])
            total += subtotal
            tree.insert("", "end", values=(it["cart_id"], it["product_name"], f"{float(it['price_per_kg']):.2f}", it["qty"], f"{subtotal:.2f}"))

        bottom = ttk.Frame(cart_frame, style="Card.TFrame")
        bottom.pack(fill="x", padx=8, pady=(8, 12))
        ttk.Label(bottom, text=f"Total: ₹{total:.2f}", font=self.sub_font).pack(side="left", padx=8)
        ttk.Button(bottom, text="Remove Selected", command=lambda: self._remove_selected_from_cart_db(tree)).pack(side="right", padx=6)
        ttk.Button(bottom, text="Clear Cart", command=self._clear_cart_db).pack(side="right", padx=6)
        ttk.Button(bottom, text="Checkout (demo)", style="Accent.TButton", command=self._checkout_db).pack(side="right", padx=10)

    def _remove_selected_from_cart_db(self, tree):
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select an item to remove.")
            return
        ids = []
        for s in sel:
            vals = tree.item(s, "values")
            cart_id = int(vals[0])
            ids.append(cart_id)
        try:
            for cid in ids:
                remove_cart_item(cid)
            messagebox.showinfo("Removed", "Selected item(s) removed from cart.")
            self.show_cart()
        except Exception as e:
            messagebox.showerror("DB Error", f"Failed to remove item(s): {e}")

    def _clear_cart_db(self):
        if not self.consumer_id:
            return
        if messagebox.askyesno("Confirm", "Clear all items from cart?"):
            try:
                clear_cart_for_consumer(self.consumer_id)
                messagebox.showinfo("Cleared", "Cart cleared.")
                self.show_cart()
            except Exception as e:
                messagebox.showerror("DB Error", f"Failed to clear cart: {e}")

    def _checkout_db(self):
        if not self.consumer_id:
            return
        items = fetch_cart_for_consumer(self.consumer_id)
        if not items:
            messagebox.showwarning("Empty", "Cart is empty.")
            return
        total = sum(float(it["price_per_kg"]) * int(it["qty"]) for it in items)
        # demo checkout: just clear cart
        if messagebox.askyesno("Checkout", f"Proceed to demo checkout? Total: ₹{total:.2f}"):
            try:
                clear_cart_for_consumer(self.consumer_id)
                messagebox.showinfo("Checkout", f"Demo checkout complete. Total: ₹{total:.2f}\nThank you, {self.consumer_name}!")
                self.show_home()
            except Exception as e:
                messagebox.showerror("DB Error", f"Checkout failed: {e}")


if __name__ == "__main__":
    app = CropPortalApp()
    app.mainloop()
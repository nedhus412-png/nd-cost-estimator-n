from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import sqlite3
import csv
import io
import json

app = FastAPI(title="Yaho Construction Cost Estimator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE = "cost_estimator.db"

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS materials
                 (id INTEGER PRIMARY KEY, 
                  name TEXT UNIQUE, 
                  category TEXT,
                  unit TEXT,
                  description TEXT,
                  created_at TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS suppliers
                 (id INTEGER PRIMARY KEY,
                  name TEXT UNIQUE,
                  contact TEXT,
                  email TEXT,
                  phone TEXT,
                  payment_terms TEXT,
                  reliability_rating REAL,
                  average_delivery_days INTEGER,
                  created_at TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS supplier_prices
                 (id INTEGER PRIMARY KEY,
                  supplier_id INTEGER,
                  material_id INTEGER,
                  unit_price REAL,
                  minimum_quantity INTEGER,
                  currency TEXT,
                  last_updated TIMESTAMP,
                  FOREIGN KEY(supplier_id) REFERENCES suppliers(id),
                  FOREIGN KEY(material_id) REFERENCES materials(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS estimates
                 (id INTEGER PRIMARY KEY,
                  project_name TEXT,
                  description TEXT,
                  created_at TIMESTAMP,
                  updated_at TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS estimate_items
                 (id INTEGER PRIMARY KEY,
                  estimate_id INTEGER,
                  material_id INTEGER,
                  quantity REAL,
                  supplier_id INTEGER,
                  unit_price REAL,
                  total_price REAL,
                  FOREIGN KEY(estimate_id) REFERENCES estimates(id),
                  FOREIGN KEY(material_id) REFERENCES materials(id),
                  FOREIGN KEY(supplier_id) REFERENCES suppliers(id))''')
    
    conn.commit()
    conn.close()

init_db()

class Material(BaseModel):
    name: str
    category: str
    unit: str
    description: Optional[str] = ""

class Supplier(BaseModel):
    name: str
    contact: str
    email: str
    phone: str
    payment_terms: str
    reliability_rating: float
    average_delivery_days: int

class SupplierPrice(BaseModel):
    supplier_id: int
    material_id: int
    unit_price: float
    minimum_quantity: int
    currency: str = "ETB"

class EstimateItem(BaseModel):
    material_id: int
    quantity: float
    supplier_id: int

class Estimate(BaseModel):
    project_name: str
    description: str
    items: List[EstimateItem]

@app.post("/materials")
def create_material(material: Material):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO materials (name, category, unit, description, created_at)
                     VALUES (?, ?, ?, ?, ?)''',
                  (material.name, material.category, material.unit, material.description, datetime.now()))
        conn.commit()
        material_id = c.lastrowid
        conn.close()
        return {"id": material_id, **material.dict()}
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Material already exists")

@app.get("/materials")
def get_materials(category: Optional[str] = None):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    if category:
        c.execute("SELECT * FROM materials WHERE category = ?", (category,))
    else:
        c.execute("SELECT * FROM materials")
    materials = c.fetchall()
    conn.close()
    return [{"id": m[0], "name": m[1], "category": m[2], "unit": m[3], "description": m[4]} for m in materials]

@app.get("/materials/categories")
def get_categories():
    categories = [
        "Cement & Concrete",
        "Steel & Metal",
        "Aggregates",
        "Electrical",
        "Plumbing",
        "Timber & Wood",
        "Glass & Ceramics",
        "Paint & Finishing",
        "Hardware",
        "Masonry",
        "Insulation",
        "Other"
    ]
    return {"categories": categories}

@app.post("/suppliers")
def create_supplier(supplier: Supplier):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO suppliers (name, contact, email, phone, payment_terms, reliability_rating, average_delivery_days, created_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (supplier.name, supplier.contact, supplier.email, supplier.phone, supplier.payment_terms, 
                   supplier.reliability_rating, supplier.average_delivery_days, datetime.now()))
        conn.commit()
        supplier_id = c.lastrowid
        conn.close()
        return {"id": supplier_id, **supplier.dict()}
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Supplier already exists")

@app.get("/suppliers")
def get_suppliers():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT * FROM suppliers")
    suppliers = c.fetchall()
    conn.close()
    return [{"id": s[0], "name": s[1], "contact": s[2], "email": s[3], "phone": s[4], 
             "payment_terms": s[5], "reliability_rating": s[6], "average_delivery_days": s[7]} for s in suppliers]

@app.get("/suppliers/{supplier_id}")
def get_supplier(supplier_id: int):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,))
    supplier = c.fetchone()
    conn.close()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return {"id": supplier[0], "name": supplier[1], "contact": supplier[2], "email": supplier[3], 
            "phone": supplier[4], "payment_terms": supplier[5], "reliability_rating": supplier[6], 
            "average_delivery_days": supplier[7]}

@app.post("/prices")
def add_price(price: SupplierPrice):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''INSERT INTO supplier_prices (supplier_id, material_id, unit_price, minimum_quantity, currency, last_updated)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (price.supplier_id, price.material_id, price.unit_price, price.minimum_quantity, price.currency, datetime.now()))
    conn.commit()
    price_id = c.lastrowid
    conn.close()
    return {"id": price_id, **price.dict()}

@app.get("/prices/material/{material_id}")
def get_material_prices(material_id: int):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''SELECT sp.id, s.id, s.name, sp.unit_price, sp.minimum_quantity, sp.currency, 
                        s.average_delivery_days, s.reliability_rating, s.payment_terms
                 FROM supplier_prices sp
                 JOIN suppliers s ON sp.supplier_id = s.id
                 WHERE sp.material_id = ?
                 ORDER BY sp.unit_price ASC''', (material_id,))
    prices = c.fetchall()
    conn.close()
    return [{"price_id": p[0], "supplier_id": p[1], "supplier_name": p[2], "unit_price": p[3], 
             "minimum_quantity": p[4], "currency": p[5], "delivery_days": p[6], 
             "reliability": p[7], "payment_terms": p[8]} for p in prices]

@app.post("/prices/bulk-import")
async def bulk_import_prices(file: UploadFile = File(...)):
    contents = await file.read()
    stream = io.StringIO(contents.decode('utf-8'))
    reader = csv.DictReader(stream)
    
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    imported = 0
    errors = []
    
    for row in reader:
        try:
            c.execute('''INSERT INTO supplier_prices (supplier_id, material_id, unit_price, minimum_quantity, currency, last_updated)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (int(row['supplier_id']), int(row['material_id']), float(row['unit_price']), 
                       int(row.get('minimum_quantity', 1)), row.get('currency', 'ETB'), datetime.now()))
            imported += 1
        except Exception as e:
            errors.append(f"Row error: {str(e)}")
    
    conn.commit()
    conn.close()
    return {"imported": imported, "errors": errors}

@app.post("/estimates")
def create_estimate(estimate: Estimate):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    c.execute('''INSERT INTO estimates (project_name, description, created_at, updated_at)
                 VALUES (?, ?, ?, ?)''',
              (estimate.project_name, estimate.description, datetime.now(), datetime.now()))
    estimate_id = c.lastrowid
    
    total_cost = 0
    for item in estimate.items:
        c.execute("SELECT unit_price FROM supplier_prices WHERE supplier_id = ? AND material_id = ?",
                  (item.supplier_id, item.material_id))
        price_row = c.fetchone()
        unit_price = price_row[0] if price_row else 0
        total_price = unit_price * item.quantity
        total_cost += total_price
        
        c.execute('''INSERT INTO estimate_items (estimate_id, material_id, quantity, supplier_id, unit_price, total_price)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (estimate_id, item.material_id, item.quantity, item.supplier_id, unit_price, total_price))
    
    conn.commit()
    conn.close()
    return {"id": estimate_id, "project_name": estimate.project_name, "total_cost": total_cost}

@app.get("/estimates/{estimate_id}")
def get_estimate(estimate_id: int):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    c.execute("SELECT * FROM estimates WHERE id = ?", (estimate_id,))
    estimate = c.fetchone()
    if not estimate:
        conn.close()
        raise HTTPException(status_code=404, detail="Estimate not found")
    
    c.execute('''SELECT ei.id, m.name, ei.quantity, m.unit, s.name, ei.unit_price, ei.total_price
                 FROM estimate_items ei
                 JOIN materials m ON ei.material_id = m.id
                 JOIN suppliers s ON ei.supplier_id = s.id
                 WHERE ei.estimate_id = ?''', (estimate_id,))
    items = c.fetchall()
    conn.close()
    
    total = sum(item[6] for item in items)
    
    return {
        "id": estimate[0],
        "project_name": estimate[1],
        "description": estimate[2],
        "items": [{"id": i[0], "material": i[1], "quantity": i[2], "unit": i[3], 
                   "supplier": i[4], "unit_price": i[5], "total_price": i[6]} for i in items],
        "total_cost": total,
        "created_at": estimate[3]
    }

@app.get("/estimates")
def list_estimates():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''SELECT e.id, e.project_name, e.description, e.created_at, 
                        SUM(ei.total_price) as total
                 FROM estimates e
                 LEFT JOIN estimate_items ei ON e.id = ei.estimate_id
                 GROUP BY e.id
                 ORDER BY e.created_at DESC''')
    estimates = c.fetchall()
    conn.close()
    return [{"id": e[0], "project_name": e[1], "description": e[2], "created_at": e[3], "total_cost": e[4]} 
            for e in estimates]

@app.get("/compare/material/{material_id}")
def compare_suppliers(material_id: int):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    c.execute('''SELECT sp.supplier_id, s.name, sp.unit_price, s.payment_terms, 
                        s.average_delivery_days, s.reliability_rating, sp.minimum_quantity
                 FROM supplier_prices sp
                 JOIN suppliers s ON sp.supplier_id = s.id
                 WHERE sp.material_id = ?
                 ORDER BY sp.unit_price ASC''', (material_id,))
    
    prices = c.fetchall()
    conn.close()
    
    if not prices:
        raise HTTPException(status_code=404, detail="No supplier prices found for this material")
    
    return [{"supplier_id": p[0], "supplier_name": p[1], "unit_price": p[2], "payment_terms": p[3],
             "delivery_days": p[4], "reliability_rating": p[5], "minimum_quantity": p[6],
             "price_rank": i+1} for i, p in enumerate(prices)]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

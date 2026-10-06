from flask import Blueprint, request, jsonify
from db import get_db_connection, release_db_connection

products_bp = Blueprint('products', __name__)

@products_bp.route('', methods=['GET'])
def get_products():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    if per_page > 100:
        per_page = 100
    offset = (page - 1) * per_page
    category = request.args.get('category')

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500

    try:
        cur = conn.cursor()
        if category:
            cur.execute("SELECT id, name, description, price, category FROM products WHERE category = ? LIMIT ? OFFSET ?", (category, per_page, offset))
        else:
            cur.execute("SELECT id, name, description, price, category FROM products LIMIT ? OFFSET ?", (per_page, offset))
        
        rows = cur.fetchall()
        products = [
            {"id": row[0], "name": row[1], "description": row[2], "price": float(row[3]), "category": row[4]} 
            for row in rows
        ]
        
        if category:
            cur.execute("SELECT COUNT(*) FROM products WHERE category = ?", (category,))
        else:
            cur.execute("SELECT COUNT(*) FROM products")
        total_count = cur.fetchone()[0]

        return jsonify({
            'products': products,
            'page': page,
            'per_page': per_page,
            'total': total_count
        })
    finally:
        release_db_connection(conn)

@products_bp.route('/<int:product_id>', methods=['GET'])
def get_product(product_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500

    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, description, price, category FROM products WHERE id = ?", (product_id,))
        row = cur.fetchone()
        if row:
            product = {"id": row[0], "name": row[1], "description": row[2], "price": float(row[3]), "category": row[4]}
            return jsonify(product)
        else:
            return jsonify({'error': 'Product not found'}), 404
    finally:
        release_db_connection(conn)

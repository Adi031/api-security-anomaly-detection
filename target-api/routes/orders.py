from flask import Blueprint, request, jsonify, g
from db import get_db_connection, release_db_connection
from routes.auth import token_required

orders_bp = Blueprint('orders', __name__)

@orders_bp.route('', methods=['POST'])
@token_required
def create_order():
    data = request.get_json()
    if not data or 'product_id' not in data or 'quantity' not in data or 'total_price' not in data:
        return jsonify({'error': 'Missing required fields'}), 400
    
    product_id = data['product_id']
    quantity = data['quantity']
    total_price = data['total_price']

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500

    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO orders (user_id, product_id, quantity, total_price, status) VALUES (?, ?, ?, ?, 'pending')",
            (g.user_id, product_id, quantity, total_price)
        )
        order_id = cur.lastrowid
        conn.commit()
        return jsonify({'message': 'Order created successfully', 'order_id': order_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        release_db_connection(conn)

@orders_bp.route('', methods=['GET'])
@token_required
def list_orders():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    offset = (page - 1) * per_page

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500

    try:
        cur = conn.cursor()
        cur.execute("SELECT id, total_price, status, created_at FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?", (g.user_id, per_page, offset))
        rows = cur.fetchall()
        orders = [
            {"id": row[0], "total_price": float(row[1]), "status": row[2], "created_at": row[3]} 
            for row in rows
        ]
        return jsonify({'orders': orders})
    finally:
        release_db_connection(conn)

@orders_bp.route('/<int:order_id>', methods=['GET'])
@token_required
def get_order(order_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500

    try:
        cur = conn.cursor()
        cur.execute("SELECT id, total_price, status, created_at, user_id FROM orders WHERE id = ?", (order_id,))
        row = cur.fetchone()
        if row:
            if row[4] != g.user_id:
                return jsonify({'error': 'Forbidden'}), 403
            order = {"id": row[0], "total_price": float(row[1]), "status": row[2], "created_at": row[3]}
            return jsonify(order)
        else:
            return jsonify({'error': 'Order not found'}), 404
    finally:
        release_db_connection(conn)

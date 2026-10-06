from flask import Blueprint, request, jsonify, g
from db import get_db_connection, release_db_connection
from routes.auth import token_required

users_bp = Blueprint('users', __name__)

@users_bp.route('/<int:user_id>/profile', methods=['GET'])
@token_required
def get_profile(user_id):
    if g.user_id != user_id:
        return jsonify({'error': 'Forbidden'}), 403

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500

    try:
        cur = conn.cursor()
        cur.execute("SELECT id, username, email FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if row:
            return jsonify({"id": row[0], "username": row[1], "email": row[2]})
        else:
            return jsonify({'error': 'User not found'}), 404
    finally:
        release_db_connection(conn)

@users_bp.route('/<int:user_id>/profile', methods=['PUT'])
@token_required
def update_profile(user_id):
    if g.user_id != user_id:
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500

    try:
        cur = conn.cursor()
        if 'email' in data:
            cur.execute("UPDATE users SET email = ? WHERE id = ?", (data['email'], user_id))
        
        conn.commit()
        return jsonify({'message': 'Profile updated successfully'})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        release_db_connection(conn)

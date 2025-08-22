from flask import Flask, jsonify, request, send_file, render_template
from repository.database import db
from db_models.payment import Payment
from datetime import datetime, timedelta
from payments.pix import Pix
from flask_socketio import SocketIO

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'your_secret_key'

db.init_app(app)
socketio = SocketIO(app)

@app.route('/payment/pix', methods=['POST'])
def create_payment_pix():
    data = request.get_json()

    if 'amount' not in data:
        return jsonify({'status': 'error', 'message': 'Missing amount value.'}), 400

    amount = data.get('amount')
    expiration_date = datetime.now() + timedelta(minutes=30)  # Default to 30 minutes from now

    new_payment = Payment(
        amount=amount,
        expiration_date=expiration_date,
        status=False
    )

    pix = Pix()
    payment_info = pix.create_payment()

    new_payment.bank_payment_id = payment_info['bank_payment_id']
    new_payment.qr_code = payment_info['qr_code_path']

    db.session.add(new_payment)
    db.session.commit()

    return jsonify({'status': 'success', 'message': 'Payment has been created successfully.', 'payment_id': new_payment.to_dict()})


@app.route('/payments/pix/qr_code/<file_name>', methods=['GET'])
def get_pix_qr_code(file_name):
    return send_file(f'static/qr_codes/{file_name}.png', mimetype='image/png')


@app.route('/payment/pix/confirmation', methods=['POST'])
def pix_confirmation():

    data = request.get_json()

    if 'bank_payment_id' not in data or 'amount' not in data:
        return jsonify({'status': 'error', 'message': 'Missing payment data.'}), 400

    payment = Payment.query.filter_by(bank_payment_id=data.get('bank_payment_id')).first()

    if not payment:
        return jsonify({'status': 'error', 'message': 'Payment not found.'}), 404
    
    if payment.status:
        return jsonify({'status': 'error', 'message': 'Payment has already been confirmed.'}), 400


    if data.get('amount') != payment.amount:
        return jsonify({'status': 'error', 'message': 'Invalid payment amount.'}), 400

    payment.status = True
    payment.expiration_date = datetime.now()  # Mark as confirmed by setting expiration to now
    db.session.commit()

    socketio.emit(f'payment_confirmed-{payment.id}')

    return jsonify({'status': 'success', 'message': 'Payment has been confirmed successfully.'})


@app.route('/payments/pix/<payment_id>', methods=['GET'])
def payment_pix_page(payment_id):
    payment = db.session.get(Payment, payment_id)

    if not payment:
        return render_template('404.html'), 404

    if payment.status:
        return render_template('confirmed_payment.html',
                                payment=payment,
                                amount=payment.amount,
                                host='http://127.0.0.1:5000',
                                qr_code=payment.qr_code)

    return render_template('payment.html',
                            payment=payment,
                            amount=payment.amount,
                            host='http://127.0.0.1:5000',
                            qr_code=payment.qr_code)

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    socketio.run(app, debug=True)
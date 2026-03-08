from flask_mail import Mail, Message

mail = Mail()

def send_notification(app, subject, recipient, body):

    with app.app_context():

        msg = Message(
            subject,
            recipients=[recipient],
            body=body
        )

        mail.send(msg)
from flask import Flask
from flask_cors import CORS


import config

from extensions import db, socketio



app = Flask(__name__)

app.config.from_object(config)


CORS(
    app,
    supports_credentials=True
)



db.init_app(app)


socketio.init_app(
    app,
    cors_allowed_origins=config.SOCKET_CORS
)



from api import event_bp, dashboard_bp


app.register_blueprint(
    event_bp
)

app.register_blueprint(
    dashboard_bp
)



import services.ws_handler



from services.scheduler import start_scheduler


start_scheduler(app)



from api.event_api import create_alarm_record


app.create_alarm = create_alarm_record



if __name__ == "__main__":

    with app.app_context():

        db.create_all()


    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=True
    )
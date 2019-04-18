from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)
migrate = Migrate(app, db)

login = LoginManager(app)
login.login_view = 'login'

# app.config['DOWNLOAD_FOLDER'] = '/Users/ksgifford/ischool/W210/W210_Final/flaskapp/app/downloads/'
app.config['DOWNLOAD_FOLDER'] = '/home/ubuntu/W210_Final/flaskapp/app/downloads/'
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

from app import routes, models

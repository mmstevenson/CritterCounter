from flask import render_template, flash, redirect, url_for, request, send_file, send_from_directory
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from werkzeug.urls import url_parse
from app import app
from app.forms import LoginForm
import boto3
from flask_login import current_user, login_user, logout_user, login_required
from app.models import User
import csv
import shutil
import requests
import json
import os
import pandas as pd
import numpy as np
import exifread

s3_client = boto3.client('s3')
bucket_name = 'w210-img-upload'

s3_resource = boto3.resource('s3')
my_bucket = s3_resource.Bucket(bucket_name)

db_string = "postgres://dbmaster:dbpa$$w0rd!@w210postgres01.c8siy60gz3hg.us-east-1.rds.amazonaws.com:5432/w210results"

def df_to_geojson(df, properties, lat='Lat', lon='Long'):
    geojson = {'type':'FeatureCollection', 'features':[]}
    for _, row in df.iterrows():
        feature = {'type':'Feature',
                   'properties':{},
                   'geometry':{'type':'Point',
                               'coordinates':[]}}
        feature['geometry']['coordinates'] = [row[lon],row[lat]]
        for prop in properties:
            feature['properties'][prop] = row[prop]
        geojson['features'].append(feature)
    return geojson

def gpsParser(x):
    if x == 0.0:
        return 0.0
    else:
        degrees = int(x[1:-1].split(',')[0])
        minNumerator = int(x[1:-1].split(',')[1].split('/')[0])
        minDenominator = int(x[1:-1].split(',')[1].split('/')[1])
        deciMinutes = minNumerator/minDenominator/60
        return(np.round(degrees+deciMinutes,6))

def exifExtractor(file):
    image = open(file, 'rb')
    tags = exifread.process_file(image)
    gpsInfo = {'fileName': image.name.lower().split('/')[-1]}
    for k in ['GPS GPSLatitudeRef', 'GPS GPSLatitude', 'GPS GPSLongitudeRef', 'GPS GPSLongitude']:
        try:
            gpsInfo[k] = str(tags[k])
        except KeyError:
            gpsInfo[k] = 0.0

    return gpsInfo

def formatLabel(x):
    if x == 'american_black_bear':
        return 'Black bear'
    elif x == 'domestic_cow':
        return 'Cow'
    elif x == 'domestic_dog':
        return 'Dog'
    elif x == 'gray_fox':
        return 'Gray fox'
    elif x == 'red_fox':
        return 'Red fox'
    elif x == 'white_tailed_deer':
        return 'White-tailed deer'
    elif x == 'mule_deer':
        return 'Mule deer'
    elif x == 'wild_turkey':
        return 'Wild turkey'
    elif x == 'red_deer':
        return 'Elk'
    else:
        return x.capitalize()

@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', title='Home')

@app.route('/about')
def about():
    return render_template('about.html', title='About Us')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('upload'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('upload')
        return redirect(next_page)
    return render_template('login_page.html', title='Sign In', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        data_files = request.files.getlist('file[]')
        for data_file in data_files:
            filename_old = current_user.username+'/upload/'+data_file.filename
            filename_new = filename_old.lower()
            s3_client.upload_fileobj(data_file, bucket_name, filename_new)
            print("Uploading "+data_file.filename+" to "+bucket_name+".")

        upload_dir = '/home/ubuntu/s3bucket/'+current_user.username+'/upload/'
        dfGPSRaw =  pd.DataFrame()
        for file in os.listdir(upload_dir):
            df_tmp = pd.DataFrame.from_dict([exifExtractor(os.path.join(upload_dir,file))],orient='columns')
            dfGPSRaw = dfGPSRaw.append(df_tmp)

        dfGPSRaw['LatRef'] = dfGPSRaw['GPS GPSLatitudeRef'].apply(lambda x: 1 if x == 'N' else -1)
        dfGPSRaw['LonRef'] = dfGPSRaw['GPS GPSLongitudeRef'].apply(lambda x: 1 if x == 'E' else -1)
        dfGPSRaw['Lat'] = dfGPSRaw['GPS GPSLatitude'].apply(gpsParser)*dfGPSRaw['LatRef']
        dfGPSRaw['Long'] = dfGPSRaw['GPS GPSLongitude'].apply(gpsParser)*dfGPSRaw['LonRef']

        dfGPStmp = dfGPSRaw[['fileName','Lat', 'Long']]
        dfGPStmp = dfGPStmp.set_index('fileName')

        geotags_file = app.config['DOWNLOAD_FOLDER']+current_user.username+'/geotags.csv'
        if os.path.isfile(geotags_file):
            dfGPSold = pd.read_csv(geotags_file)
            dfGPSnew = pd.concat([dfGPSold, dfGPStmp])
            dfGPSnew.to_csv(geotags_file)
        else:
            dfGPStmp.to_csv(geotags_file)

        return redirect(url_for('complete'))
    else:
        username = current_user.username
        return render_template('upload.html', title='File Upload', username = username)

@app.route('/complete', methods=['GET', 'POST'])
@login_required
def complete():
    if request.method == "POST":
        if 'upload_again' in request.form:
            return redirect(url_for('upload'))
        elif 'launcher' in request.form:
            return redirect(url_for('classify'))
    else:
        return render_template('complete.html', title='Thank You!')

@app.route('/output', methods=['GET', 'POST'])
@login_required
def output():
    engine = create_engine(db_string, echo=True)
    Base = declarative_base(engine)

    output_file = app.config['DOWNLOAD_FOLDER']+current_user.username+'/'+current_user.username+'_results.csv'
    # os.remove(output_file)

    class Results(Base):
        __tablename__ = 'test_upload'
        # __tablename__ = 'dummy_table'
        # __tablename__ = str(current_user.username + '_results')
        __table_args__ = {'autoload':True}

    metadata = Base.metadata
    Session = sessionmaker(bind=engine)
    session = Session()

    qry = session.query(Results)

    with open(output_file, 'w') as csvfile:
        outcsv = csv.writer(csvfile, delimiter=',',quotechar='"', quoting = csv.QUOTE_MINIMAL)
        header = Results.__table__.columns.keys()

        outcsv.writerow(header)

        for record in qry.all():
            outcsv.writerow([getattr(record, c) for c in header ])

    df_results = pd.read_csv(output_file)
    df_resTransform = df_results.loc[df_results.groupby(['fileName'])['probability'].idxmax()]
    dfGPS = pd.read_csv(app.config['DOWNLOAD_FOLDER']+current_user.username+'/geotags.csv')
    df_output = pd.merge(df_resTransform, dfGPS, on='fileName')
    df_output = df_output[['fileName', 'label', 'probability', 'userId', 'Lat', 'Long']]
    df_output['label'] = df_output['label'].apply(formatLabel)
    geojson = df_to_geojson(df_output, df_output.columns)
    json_filename = app.config['DOWNLOAD_FOLDER']+current_user.username+'/species.json'
    with open(json_filename, 'w') as f:
        json.dump(geojson, f)

    session.close()
    engine.dispose()

    file_prefix = current_user.username+'/wtf'
    file_list = list(my_bucket.objects.filter(Prefix=file_prefix))[1:]
    img_dir = app.config['DOWNLOAD_FOLDER']+current_user.username+'/img'
    for obj in file_list:
        local_file_name = app.config['DOWNLOAD_FOLDER']+current_user.username+'/img/'+obj.key.split('/')[2]
        my_bucket.download_file(obj.key,local_file_name)

    shutil.make_archive(app.config['DOWNLOAD_FOLDER']+current_user.username+'/'+current_user.username+'_WTFimages','zip',img_dir)
    for file in os.listdir(img_dir):
        file_path = os.path.join(img_dir,file)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(e)

    with open(app.config['DOWNLOAD_FOLDER']+'/ConsvNW_species.json') as f:
        consvNW = json.load(f)

    df_ConsvNW = pd.read_json(app.config['DOWNLOAD_FOLDER']+'/ConsvNW_species.json', orient='columns')
    df_ConsvNW = df_ConsvNW.loc[df_ConsvNW['Lat']>0]
    species_all = df_ConsvNW[['Lat','Long']].values.tolist()

    df_bears = df_ConsvNW[df_ConsvNW['label']=='black_bear'][['Lat','Long']]
    bears = df_bears.values.tolist()

    df_elkdeer = df_ConsvNW[(df_ConsvNW['label']=='mule_deer')|(df_ConsvNW['label']=='elk')][['Lat','Long']]
    elk_deer = df_elkdeer.values.tolist()

    df_coyote = df_ConsvNW[df_ConsvNW['label']=='coyote'][['Lat','Long']]
    coyotes = df_coyote.values.tolist()

    df_cats = df_ConsvNW[(df_ConsvNW['label']=='cougar')|(df_ConsvNW['label']=='bobcat')][['Lat','Long']]
    cats = df_cats.values.tolist()

    df_chartData = pd.DataFrame(df_output['label'].value_counts()).reset_index()
    df_chartData.columns = ['name','count']
    chart_data = df_chartData.to_json(orient='records')

    payload = [geojson, species_all, bears, elk_deer, coyotes, cats, chart_data]

    return render_template('output.html', title='Results Download', data=payload)

@app.route('/classify')
@login_required
def classify():
    path = '/home/ubuntu/w210-img-upload/'+current_user.username+'/upload'
    username = current_user.username
    payload = json.dumps({'path':path, 'userId':username})
    req = requests.post("http://ec2-3-87-218-106.compute-1.amazonaws.com:5000/predictFolder", json=payload)

    test_file = app.config['DOWNLOAD_FOLDER']+current_user.username+'/'+current_user.username+'TEST.txt'
    with open(test_file, 'w') as json_file:
        json.dump(req.text, json_file)

    return redirect(url_for('output'))

@app.route('/csv_download')
@login_required
def csv_download():
    download_file = current_user.username+'_results.csv'
    return send_from_directory(app.config['DOWNLOAD_FOLDER']+current_user.username, filename=download_file, as_attachment=True)
    # return send_file(output_file, attachment_filename=output_file)

@app.route('/zip_download')
@login_required
def zip_download():
    download_zip = current_user.username+'_WTFimages.zip'
    # return send_file('downloads/'+current_user.username+'/'+download_zip, attachment_filename=download_zip)
    return send_from_directory(app.config['DOWNLOAD_FOLDER']+current_user.username, filename=download_zip, as_attachment=True)

@app.route('/save_data')
@login_required
def save_data():
    return redirect(url_for('index'))

@app.route('/purge_data')
@login_required
def purge_data():
    prefix = current_user.username+'/'
    my_bucket.objects.filter(Prefix=prefix).delete()
    engine = create_engine(db_string, echo=True)
    connection = engine.connect()
    connection.execute("DROP TABLE IF EXISTS {}".format('test_upload'))
    connection.close()
    engine.dispose()
    purge_dir = os.path.join(app.config['DOWNLOAD_FOLDER'],current_user.username)
    for file in os.listdir(purge_dir):
        file_path = os.path.join(purge_dir,file)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(e)

    return redirect(url_for('index'))

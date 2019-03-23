# USAGE
# Start the server:
# 	python run_keras_server.py
# Submit a request via cURL:
# 	curl -X POST -F image=@dog.jpg 'http://localhost:5000/predict'
# Submita a request via Python:
#	python simple_request.py

# import the necessary packages
from keras.applications import ResNet50, MobileNetV2
from keras.preprocessing.image import img_to_array
from keras.applications import imagenet_utils
import pandas as pd
from sqlalchemy import create_engine
import tensorflow as tf
from PIL import Image
import numpy as np
import flask
import io
from datetime import datetime, timedelta
import time
import os
import json
import sys

# initialize our Flask application and the Keras model
app = flask.Flask(__name__)
model = None

def load_model():
    # load the pre-trained Keras model (here we are using a model
    # pre-trained on ImageNet and provided by Keras, but you can
    # substitute in your own networks just as easily)
    global model
    model = ResNet50(weights="imagenet")
    # model = MobileNetV2(weights="imagenet")
    global graph
    graph = tf.get_default_graph()

# Prep the image for prediction
def prepare_image(image, target):
    # if the image mode is not RGB, convert it
    if image.mode != "RGB":
        image = image.convert("RGB")

    # resize the input image and preprocess it
    image = image.resize(target)
    image = img_to_array(image)
    image = np.expand_dims(image, axis=0)
    image = imagenet_utils.preprocess_input(image)

    # return the processed image
    return image

# Convert the Json output to a dataframe
def convert_to_df(label_json):
    label_df = pd.DataFrame(label_json['predictions'])
    pred_df = label_df[['imageId', 'labels']]
    pred_df.index = pred_df['imageId']
    pred_df = pred_df['labels'].apply(pd.Series).reset_index(drop=False).melt('imageId', value_vars=range(5))
    pred_df = pred_df.drop('variable', axis=1)
    pred_df['imageNetId'] = pred_df['value'].apply(lambda x: x['id'])
    pred_df['label'] = pred_df['value'].apply(lambda x: x['label'])
    pred_df['probability'] = pred_df['value'].apply(lambda x: x['probability'])
    pred_df = pred_df.drop('value', axis=1)
    pred_df['rank'] = pred_df.groupby('imageId')['probability'].rank(ascending=False)
    pred_df = pred_df.sort_values(['imageId', 'rank'], ascending=[True, False])

    label_df = label_df.merge(pred_df, on='imageId', how='left').drop('labels', axis=1)
    label_df['userId'] = label_json['userId']

    return label_df


# Push results to DB
def write_df_to_db(df, table_name, conn_string = "postgres://dbmaster:dbpa$$w0rd!@w210postgres01.c8siy60gz3hg.us-east-1.rds.amazonaws.com:5432/w210results"):
    engine = create_engine(conn_string)
    engine.execute("DROP TABLE IF EXISTS {}".format(table_name))
    df.to_sql(table_name, con=engine)
    # Adding a primary key so the webserver can query the results via sqlalchemy
    with engine.connect() as con:
        con.execute("ALTER TABLE {} ADD PRIMARY KEY (index);".format(table_name))
        con.close()

    sys.stdout.write('Postgres upload complete')
    sys.stdout.flush()

# Determine which folder to move the predicted image to
def assign_new_path(labels, threshold, label_path, wtf_path):
    probs = [label["probability"] for label in labels]
    max_prob, max_id = max(probs), np.argmax(probs)
    pred = labels[max_id]["label"]
    if max_prob >= threshold:
        return os.path.join(label_path, pred)
    else:
        return wtf_path

# Move a file to a new folder
def move_to_new_path(old_file_path, new_file_path):
    # Get the new file path's directory
    new_folder = os.path.dirname(new_file_path)
    # If the new directory does not exist create it
    if not os.path.exists(new_folder):
        os.makedirs(new_folder)
    # Update the file path to the new file path
    os.rename(old_file_path, new_file_path)


@app.route("/helloWorld", methods=["GET"])
def hello_world():
    return "Hello World!!"

@app.route("/predict", methods=["POST"])
def predict():
    # initialize the data dictionary that will be returned from the
    # view

    start = time.time()

    data = {"success": False}

    # ensure an image was properly uploaded to our endpoint
    if flask.request.method == "POST":
        if flask.request.files.get("image"):
            # read the image in PIL format
            image = flask.request.files["image"].read()
            image = Image.open(io.BytesIO(image))

            # preprocess the image and prepare it for classification
            image = prepare_image(image, target=(224, 224))

            # classify the input image and then initialize the list
            # of predictions to return to the client
            with graph.as_default():
                preds = model.predict(image)
            results = imagenet_utils.decode_predictions(preds)
            data["predictions"] = []

            # loop over the results and add them to the list of
            # returned predictions
            for (imagenetID, label, prob) in results[0]:
                r = {"label": label, "probability": float(prob)}
                data["predictions"].append(r)

            # indicate that the request was a success
            data["success"] = True

            # Send classification time
            data["predict_time"] = time.time() - start

    # JSONify the response data
    response = flask.jsonify(data)

    # If specified convert data to dataframe and push to database
    df = convert_to_df(data)

    write_df_to_db(df, 'test_upload')

    # Return the json response data
    return flask.jsonify(data)

@app.route("/predictFolder", methods=["POST"])
def predict_folder():
    # initialize the data dictionary that will be returned from the
    # view
    start = time.time()

    data = {"requestSuccess": False}
    data["predictions"] = []
    data["requestTime"] = datetime.utcnow()
    # ensure an image was properly uploaded to our endpoint
    if flask.request.method == "POST":
        payload = json.loads(flask.request.json)
        if payload.get("path"):
            # ensure an image was properly uploaded to our endpoint
            path = os.path.normpath(payload.get("path"))
            base_path = os.path.dirname(path)
            label_path = os.path.join(base_path,'classified')
            wtf_path = os.path.join(base_path,'wtf')

            data["userId"] = payload.get("userId")
            for file in os.listdir(path):
                # Note the point when the script started
                pred_start = time.time()

                file_path = os.path.join(path, file)

                image_id = "{:0.6f}".format((datetime.utcnow() - datetime(1970,1,1)).total_seconds()).replace('.', '_')
                d = {'fileName':file, 'imageId':image_id}
                d['fileSuccess'] = False

                # read the image in PIL format
                image = Image.open(os.path.join(path,file))

                # preprocess the image and prepare it for classification
                image = prepare_image(image, target=(224, 224))

                # classify the input image and then initialize the list
                # of predictions to return to the client
                with graph.as_default():
                    preds = model.predict(image)
                results = imagenet_utils.decode_predictions(preds)

                # loop over the results and add them to the list of
                # returned predictions
                r = [{"id":ID, "label": label, "probability": float(prob)} for (ID, label, prob) in results[0]]
                d["labels"] = r
                d["procDatetime"] = datetime.utcnow()
                d["fileSuccess"] = True
                d["predictTime"] = time.time() - pred_start

                data["predictions"].append(d)

                sys.stdout.write(str(d['fileName']) + ': ' + str(d['predictTime']))
                sys.stdout.flush()

                # Move the file to the correct folder
                new_path = assign_new_path(r, 0.9, label_path, wtf_path)
                new_file_path = os.path.join(new_path, file)
                move_to_new_path(file_path, new_file_path)

            # indicate that the request was a success
            data["requestSuccess"] = True

            # Send classification time
            data["responseTime"] = time.time() - start

    # JSONify the response data
    response = flask.jsonify(data)

    # If specified convert data to dataframe and push to database
    sys.stdout.write('Converting data to dataframe')
    sys.stdout.flush()
    df = convert_to_df(data)

    # Write output to the database
    sys.stdout.write('Writing dataframe to Postgres database')
    sys.stdout.flush()
    write_df_to_db(df, 'test_upload')

    # return the data dictionary as a JSON response
    return flask.jsonify(data)

# if this is the main thread of execution first load the model and
# then start the server
if __name__ == "__main__":
    print(("* Loading Keras model and Flask starting server..."
        "please wait until server has fully started"))
    load_model()
    app.run(host='0.0.0.0', debug=True)

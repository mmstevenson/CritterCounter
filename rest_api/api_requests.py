# import the necessary packages
import requests
import json

# Create a class that contains all the potential api requests
class CreatureCaptureAPIRequests:
    
    def __init__(self):
        # Might be good to pass through user credentials etc here for use
        # later on
        pass

    # initialize the Keras REST API endpoint URL along with the input
    def api_request_predict_image(self, url, image_path, print_results=True):

        # load the input image and construct the payload for the request
        image = open(image_path, "rb").read()
        payload = {"image": image}

        # submit the request
        r = requests.post(url, files=payload).json()

        # ensure the request was sucessful
        if r["success"]:

            if print_results:
                # loop over the predictions and display them
                for (i, result) in enumerate(r["predictions"]):
                    print("{}. {}: {:.4f}".format(i + 1, result["label"],
                        result["probability"]))

        # otherwise, the request failed
        else:
            print("Request failed")


    def api_request_predict_folder(self, url, folder_path, print_results=False):
        # load the input image and construct the payload for the request
        payload = json.dumps({"path": folder_path})

        # submit the request
        r = requests.post(url, json=payload).json()

        # ensure the request was sucessful
        if r["success"]:
            print("Success!")
            print("Process Time: {:1.3f} seconds\n".format(r['predict_time']))

            if print_results:
                # loop over the predictions and display them
                for file, result in r["predictions"].items():
                    print("File: {}. Prediction: {} {:.4f}".format(file,
                                                                   result[0]['label'], 
                                                                   result[0]['probability']))

        # otherwise, the request failed
        else:
            print("Request failed")
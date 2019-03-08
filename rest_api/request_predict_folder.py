import requests
import json

def api_request_predict_folder(url, folder_path, user_id, print_results=False):
    print(url)
    # load the input image and construct the payload for the request
    
    payload = json.dumps({"path": folder_path, "userId": user_id})

    # submit the request
    r = requests.post(KERAS_REST_API_URL, json=payload)
    print(r)
    r = r.json()

    # ensure the request was sucessful
    if r["requestSuccess"]:
        print("Success!")
        print("Process Time: {:1.3f} seconds\n".format(r['responseTime']))
        
        if print_results:
            # loop over the predictions and display them
            for k, v in r["predictions"].items():
                print("File: {}. Prediction: {} {:.4f}".format(k,
                        v[0]['label'], v[0]['probability']))
        else:
            return r
                
    # otherwise, the request failed
    else:
        print("Request failed")

# SAMPLE REQUEST USING TEST FOLDER
# KERAS_REST_API_URL = "http://3.87.218.106:5000/predictFolder"
# FOLDER = "/home/ubuntu/rest_api/test_images"
# response = api_request_predict_folder(KERAS_REST_API_URL, FOLDER, user_id="admin", print_results=False)
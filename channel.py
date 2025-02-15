## channel.py - a simple message channel
##

from flask import Flask, request, render_template, jsonify
import json
import requests
import nltk
from nltk.tokenize import word_tokenize
from profanityfilter import ProfanityFilter
from openai import OpenAI

def generate_chat_message(prompt, chat_instance, model):
    chat_completion = chat_instance.chat.completions.create(
        messages = [
            {"role":"system","content" : "You are an Ancient Greek philosopher. Evaluate the following user stetement: "},
            {"role":"user","content" : prompt}
        ],
        model = model,
    )
    return chat_completion.choices[0].message.content

def save_messages(messages):
    global CHANNEL_FILE
    with open(CHANNEL_FILE, 'w') as f:
        json.dump(messages, f)

# Class-based application configuration
class ConfigClass(object):
    """ Flask application config """

    # Flask settings
    SECRET_KEY = 'This is an INSECURE secret!! DO NOT use this in production!!'

# Create Flask app
app = Flask(__name__)
app.config.from_object(__name__ + '.ConfigClass')  # configuration
app.app_context().push()  # create an app context before initializing db

#HUB_URL = 'http://localhost:5555'
#HUB_AUTHKEY = '1234567890'

HUB_URL = 'http://vm146.rz.uni-osnabrueck.de/hub'
HUB_AUTHKEY = 'Crr-K24d-2N'


CHANNEL_AUTHKEY = '0987654321'
CHANNEL_NAME = "philosophy chat"
#CHANNEL_ENDPOINT = "http://localhost:5001" # don't forget to adjust in the bottom of the file
#CHANNEL_ENDPOINT = "http://vm146.rz.uni-osnabrueck.de/u083/AI_and_the_web_project_3/channel.wsgi/"
CHANNEL_ENDPOINT = "http://vm146.rz.uni-osnabrueck.de/u083/channel.wsgi/"
CHANNEL_FILE = 'messages.json'
CHANNEL_TYPE_OF_SERVICE = 'aiweb24:chat'
MAX_MESSAGE_NUMBER = 10

# Openai/llama API configuration
API_KEY = 'becc06335fb9111827b944a3a90546d6' # Replace with your API key
BASE_URL = "https://chat-ai.academiccloud.de/v1"
MODEL = "meta-llama-3.1-8b-instruct" # Choose any available model

# Start OpenAI client
client = OpenAI(
     api_key = API_KEY,
     base_url = BASE_URL
)


@app.cli.command('register')
def register_command():
    global CHANNEL_AUTHKEY, CHANNEL_NAME, CHANNEL_ENDPOINT

    # send a POST request to server /channels
    response = requests.post(HUB_URL + '/channels', headers={'Authorization': 'authkey ' + HUB_AUTHKEY},
                             data=json.dumps({
                                "name": CHANNEL_NAME,
                                "endpoint": CHANNEL_ENDPOINT,
                                "authkey": CHANNEL_AUTHKEY,
                                "type_of_service": CHANNEL_TYPE_OF_SERVICE,
                             }))

    if response.status_code != 200:
        print("Error creating channel: "+str(response.status_code))
        print(response.text)
        return
    else:
      
        initial_messages = []

        initial_messages.append(
            {'content': "This is an Ancient philosophy chat. The total number of messages here is limited to " + str(MAX_MESSAGE_NUMBER) +
            ". Be polite and do not mention two putatively great continental philosophers whose names start with H.",
            'sender': "System",
            'timestamp': "",
            'extra': "",
            })

        initial_messages.append(
            {'content': "Just acts are allotrion agathon i.e. foreign good. He who acts most justly is he who is the dumbest.",
            'sender': "Thrasymachus",
            'timestamp': "",
            'extra': "",
            })

        initial_messages.append(
            {'content': "In an ideal polity, he who acts justly acts in accordance with the expectations to his social role und thus contributes to the maintenance of that ideal polity. Living in such a polity is good for all its citizens. So just acts are both foreign and one's own good.",
            'sender': "Socrates",
            'timestamp': "",
            'extra': "",
            })
        
        save_messages(initial_messages)

def check_authorization(request):
    global CHANNEL_AUTHKEY
    # check if Authorization header is present
    if 'Authorization' not in request.headers:
        return False
    # check if authorization header is valid
    if request.headers['Authorization'] != 'authkey ' + CHANNEL_AUTHKEY:
        return False
    return True

@app.route('/health', methods=['GET'])
def health_check():
    global CHANNEL_NAME
    if not check_authorization(request):
        return "Invalid authorization", 400
    return jsonify({'name':CHANNEL_NAME}),  200

# GET: Return list of messages
@app.route('/', methods=['GET'])
def home_page():
    if not check_authorization(request):
        return "Invalid authorization", 400
    # fetch channels from server
    return jsonify(read_messages())

# POST: Send a message
@app.route('/', methods=['POST'])
def send_message():
    
    # fetch channels from server
    # check authorization header
    if not check_authorization(request):
        return "Invalid authorization", 400
    # check if message is present
    message = request.json
    if not message:
        return "No message", 400
    if not 'content' in message:
        return "No content", 400
    
    message_tokens = word_tokenize(message["content"])

    #lower bound on the number of words in a message
    if len(message_tokens) <= 5:
        return "I appreciate your laconic way of though expression. We are however in Attica, so please be more elaborate i.e use more than 5 words in what you post.", 400
    #upper bound on the number of words in a message
    if len(message_tokens) >= 100:
        return "Although we are in Attica, try to be more laconic i.e. use fewer than 100 words in your message.", 400
    if not 'sender' in message:
        return "No sender", 400
    if not 'timestamp' in message:
        return "No timestamp", 400
    if not 'extra' in message:
        extra = None
    else:
        extra = message['extra']
    


    
    messages = read_messages()

   
       

    #censor the new message using the profanity filter
    pf = ProfanityFilter(extra_censor_list=["Hegel", "Heidegger"])
    message["content"] = pf.censor(message["content"])
    # add new message to messages
    messages.append({'content': message['content'],
                     'sender': message['sender'],
                     'timestamp': message['timestamp'],
                     'extra': extra,
                     })
    
    #add an LLM-generated response to messages
    response = generate_chat_message(message["content"], client, MODEL)
    print (response)
    messages.append({'content': response,
                     'sender': "LLM",
                     'timestamp': message['timestamp'],
                     'extra': extra,
                     })
    
    #delete old messages
    #until total number thereof
    #obeys the upper bound on the total
    #number of messages
    while len(messages) > MAX_MESSAGE_NUMBER:
        messages.pop(0)
    save_messages(messages)
    return "OK", 200

def read_messages():
    global CHANNEL_FILE
    try:
        f = open(CHANNEL_FILE, 'r')
    except FileNotFoundError:
        return []
    try:
        messages = json.load(f)
    except json.decoder.JSONDecodeError:
        messages = []
    f.close()
    return messages



# Start development web server
# run flask --app channel.py register
# to register channel with hub

if __name__ == '__main__':
    app.run(port=5001, debug=True)

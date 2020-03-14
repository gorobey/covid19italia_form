from flask import Flask, request
import requests
import yaml, json
import credentials
import re

with open('italy_geo.json') as f:
  italy_geo = json.load(f)

app = Flask(__name__)

# Authentication for user filing issue (must have read/write access to
# repository to add issue to)
USERNAME = credentials.user
PASSWORD = credentials.password

# The repository to add this issue to
REPO_OWNER = 'emergenzeHack'
REPO_NAME = 'covid19italia_segnalazioni'


@app.route('/')
def paynoattention():
    return 'Pay no attention to that man behind the curtain.'

@app.route('/report', methods=['POST'])
def process_report():
    labels = []
    payload = request.json

    # Rimuovi nome gruppo dal nome delle chiavi
    # e.g. datibancari/iban -> datibancari
    for key_name in list(payload):
        if "datibancari/" in key_name:
            new_key_name = key_name.replace("datibancari/","")
            payload[new_key_name] = payload[key_name]
            payload.pop(key_name)

    label=request.headers.get('label')

    # Assegna le label in base alle selezioni sul form "Iniziative"
    if label == "iniziativa":
        if "Natura" in list(payload):
            if payload["Natura"] == "culturale-ricr":
                label = "Attivita culturali e ricreative"
            elif payload["Natura"] == "solidale":
                label = "Servizi e iniziative solidali "
                if "Tipo_di_soggetto" in list(payload):
                    if payload["Tipo_di_soggetto"] == "privato":
                        label += "private"
                    else:
                        label += "pubbliche"
            elif payload["Natura"] == "didattica":
                label = "Didattica a distanza e-learning"
            elif payload["Natura"] == "sostegno-lavor":
                label = "Sostegno lavoro e imprese"

    # Prepara il titolo dell'Issue
    if "Titolo" in list(payload):
        issue_title=payload["Titolo"][0:100]
    elif "Cosa" in list(payload):
        issue_title=payload["Cosa"][0:100]
    elif "Testo" in list(payload):
        issue_title=payload["Testo"][0:100]
    elif "Descrizione" in list(payload):
        issue_title=payload["Descrizione"][0:100]
    else:
        issue_title=label

    # Se trovi riferimenti a psicologi o psicoterapeuti, 
    #  aggiungi la label "Supporto Psicologico"
    if "Titolo" in list(payload):
        if "psicolog" in payload["Titolo"].lower() or "psicoter" in payload["Titolo"].lower():
                labels.append("Supporto Psicologico")
        else:
            if "Descrizione" in list(payload):
                if "psicolog" in payload["Descrizione"].lower() or "psicoter" in payload["Descrizione"].lower():
                    labels.append("Supporto Psicologico")
    
    location = False

    if "Indirizzo" not in list(payload) and "Posizione" not in list(payload):
        location = False
        if "Titolo" in list(payload):
            location = extract_location(payload["Titolo"])
        elif "Cosa" in list(payload) and not location:
            location = extract_location(payload["Cosa"])
        elif "Testo" in list(payload) and not location:
            location = extract_location(payload["Testo"])
        elif "Descrizione" in list(payload) and not location:
            location = extract_location(payload["Descrizione"])
        if not location:
            labels.append("Posizione mancante")

    if location:
        payload["Indirizzo"] = location
        labels.append("Posizione da verificare")

    # Aggiungi sempre la label "form" per le issue provenienti da questo script
    labels.append("form")
    # Aggiungi le label preparate
    labels.append(label)

    # Rimuovi metavalori
    stripped_payload = strip_meta(payload)

    # Prepara il payload in YAML
    yaml_payload = "<pre><yamldata>\n"+yaml.dump(stripped_payload, allow_unicode=True)+"</yamldata></pre>"

    # Apri issue su GitHub
    open_github_issue(title=issue_title, body=yaml_payload, labels=labels)

    return "OK", 200

def strip_meta(payload):
    excludelist = ["end", "start", "formhub/uuid", "meta/instanceID", "meta/deprecatedID", "Informativa"]
    # Rimuovi tutti i campi meta che iniziano con _
    for k in list(payload):
        if k.startswith('_'):
            payload.pop(k)
        # Rimuovi anche le chiavi specificate nella lista
        elif k in excludelist:
            payload.pop(k)
    return payload

def extract_location(text):
    for comune in italy_geo:
        if len(comune["comune"]) > 3 and comune["comune"] in text:
            print("Trovato riferimento a comune", comune["comune"])
            location = comune["lat"] + " " + comune["lng"]
            print("Aggiungo", location)
            return location

    return False

def open_github_issue(title, body=None, assignee=None, milestone=None, labels=[]):
    '''Create an issue on github.com using the given parameters.'''
    # Our url to create issues via POST
    url = 'https://api.github.com/repos/%s/%s/issues' % (REPO_OWNER, REPO_NAME)
    # Create an authenticated session to create the issue
    session = requests.Session()
    session.auth = (USERNAME, PASSWORD)
    # Create our issue
    issue = {'title': title,
             'body': body,
             'assignee': assignee,
             'milestone': milestone,
             'labels': labels}

    # Add the issue to our repository
    r = session.post(url, json.dumps(issue))
    
    if r.status_code == 201:
        print('Successfully created Issue', title)
    else:
        print('Could not create Issue', title)
        print('Response:', r.content)


app.run(host='0.0.0.0');

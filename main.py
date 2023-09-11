from datetime import datetime
import json
from flask import Flask
import firestore_services as fs
import settings as st
import fhir_controller as fc
import medOpt_controller as MO
import version as ver
import sys
import logging
from encryption_services import EncryptionServices

app = Flask(__name__)
FireStoreService = fs.FirestoreService()

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)

def saveInterventionToFirestore(user, FHIRdata, MedOptBody, medOptResponse, messages):
    data = {
        '_dateCreated': datetime.utcnow(),
        '__fhirData': FHIRdata,
        '_age': FHIRdata['patient']['patientForBackend']['age'],
        '_authStatus': FHIRdata['_authStatus'],
        '_authResponse': user['_authResponse'],
        '_dateUpdated': datetime.utcnow(),
        '_medOptDate': datetime.utcnow(),
        '_medOptScore': medOptResponse['totalScore'],
        '_nyhaValue': user['_nyhaValue'],
        '_site': user['site'],
        '_sendEmail': True,
        '_participantEmail': user['_email_orig'],
        '_type': 'auto',
        '_userId': user['document_id'],
        'medOptBody': MedOptBody,
        'medOptResponse': medOptResponse,
        'messages': messages,
        'version': ver.version
    }
    json_data = json.dumps(data, cls=DateTimeEncoder)
    result = FireStoreService.saveInterventionToFirestore(user['document_id'], data)
    return result

@app.get("/")
def main():
    print(f"Start version: {ver.version} : {sys.version}, at time {datetime.now()}")
    targeted_users = FireStoreService.findTargetedUser()
    for targeted_user in targeted_users:
        fhir = fc.fhir_controller(targeted_user, FireStoreService)
        fhirData = fhir.formFHIRdata()
        targeted_user['_authResponse'] = fhir.authResponse
        # print(fhirData)
        if fhirData['_authStatus']:
            medOpt = MO.medOpt_controller(fhirData)
            # print(medOpt.medOptBody)
            # print(medOpt.medOptResponse)
            # print(medOpt.medOptMessages)
            saveInterventionToFirestore(targeted_user, fhirData, medOpt.medOptBody, medOpt.medOptResponse,
                                        medOpt.medOptMessages)
        else:
            print("NO MOS process.")
    return f'Done version: {ver.version} : {sys.version}'

if __name__ == "__main__":
    if st.DB_SITE == "local-dev" or st.DB_SITE == "local-prod":
        main()
    else:
        app.run(debug=True)

from datetime import datetime, timedelta
import sys
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from encryption_services import EncryptionServices
import os
import settings as st


class FirestoreService:
    project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', None)

    default_app = None
    db = None
    encryption_services = EncryptionServices()
    def __init__(self):
        try:
            if st.DB_SITE == "local-dev":
                cred = credentials.Certificate("smarthfdev-dbb9fd1c0131.json")
            elif st.DB_SITE == "local-prod":
                cred = credentials.Certificate("smarthfprod-db.json")
            else:
                cred = credentials.ApplicationDefault()

            self.default_app = firebase_admin.initialize_app(cred, {
                'projectId': self.project_id,
            })
            # self.default_app = firebase_admin.initialize_app(self.cred)
        except Exception as e:
            print(f"Error in FirestorePatientController.__init_: {sys.exc_info()}")

        self.db = firestore.client(self.default_app)

    def get_all_documents_from_collection(self, collection_name):
        result = []

        try:
            result = self.db.collection(collection_name).get()
        except BaseException as e:
            print(f"Error in get_all_documents_from_collection: {sys.exc_info()}")
            raise e

        return result

    def get_all_users(self):
        try:
            r = self.db.collection('users').order_by('_epicId').where('_epicId', '!=', '')
            result = [doc.to_dict() for doc in r.stream()]
        except BaseException as e:
            print(f"Error in get_all_users: {sys.exc_info()}")
            raise e

        return result

    def findTargetedUser(self):
        if st.Test_mode:
            all_users = self.db.collection('users').where('_userId', '==', st.Test_doc)
        else:
            all_users = self.db.collection('users').where('_epicId', '!=', '').order_by('_epicId')
        dates_user_epic_id = {}
        users_short = {}
        for user_doc in all_users.stream():
            doc_id = user_doc.id
            user_doc_dict = user_doc.to_dict()
            try:
                first_intervention = self.get_user_latest_manual_intervention(doc_id)
                user_doc_dict['refresh_token'] = first_intervention['refresh_token']
                user_doc_dict['_nyhaValue'] = first_intervention['_nyhaValue']
            except Exception as e:
                print(f"Error in getting user first manual intervention, user doc:{doc_id}")
                continue

            user_doc_decrypted = {}
            try:
                user_doc_decrypted = self.encryption_services.decrypt_dict(user_doc_dict)
            except Exception as e:
                print(f"user doc decryption failed, user doc:{doc_id}")
                continue

            dateCreated = user_doc_decrypted.get('_dateCreated', None)
            user_epic_id = user_doc_decrypted.get('_epicId', None)
            visitDate = user_doc_decrypted.get('_visitDate', None)
            email = user_doc_decrypted.get('_email', None)
            site = user_doc_decrypted.get('_organizationId', None)
            refresh_token = user_doc_decrypted.get('refresh_token', None)
            nyhaValue = user_doc_decrypted.get('_nyhaValue', None)
            email_orig = user_doc_dict.get('_email', None)
            offset = user_doc_dict.get('_visitDateOffset', -4)

            # If the user ID has not been seen before, store the created date
            if user_epic_id not in dates_user_epic_id:
                dates_user_epic_id[user_epic_id] = dateCreated
                users_short[user_epic_id] = {"document_id": doc_id, "_visitDate": visitDate,
                                             "_createdDate": dateCreated, "_email": email, "site": site,
                                             "refresh_token": refresh_token, "_nyhaValue": nyhaValue,
                                             "_email_orig": email_orig, "offset": offset}
            else:
                # If the user ID has been seen before, update the latest created date if the current date is newer
                if dateCreated > dates_user_epic_id[user_epic_id]:
                    dates_user_epic_id[user_epic_id] = dateCreated
                    users_short[user_epic_id] = {"document_id": doc_id, "_visitDate": visitDate,
                                                 "_createdDate": dateCreated, "_email": email, "site": site,
                                                 "refresh_token": refresh_token, "_nyhaValue": nyhaValue,
                                                 "_email_orig": email_orig, "offset": offset}
        print(users_short)
        # if datetime.now().date() == datetime.utcnow().date():
        #     today = (datetime.now() - timedelta(hours=4)).date()
        # else:
        #     today = datetime.now().date()

        targeted_users = []
        # Loop through the list of users and check if today is 3 days after the create_date
        for key, value in users_short.items():
            offset_value = value['offset']
            today_participant_datetime = datetime.utcnow() + timedelta(hours=offset_value)
            today_participant = today_participant_datetime.date()
            visit_date_participant_datetime = value['_visitDate'] + timedelta(hours=offset_value)
            visit_date_participant = visit_date_participant_datetime.date()
            if (today_participant - visit_date_participant).days in st.auto_run_days or st.Test_mode:
                targeted_users.append(dict(**{'_epicId': key}, **value))
                print(f"user {key} visit_date is {visit_date_participant_datetime} and today is {today_participant_datetime} in participant time zone, due for {(today_participant - visit_date_participant).days} day, running in progress")
            else:
                print(f"user {key} is on {(today_participant - visit_date_participant).days} day")
        return targeted_users

    def get_user_latest_manual_intervention(self, document_id):
        result = {}
        try:
            r = self.db.collection('users').document(document_id).collection('interventions')\
                .where('_type', '==', 'manual')\
                .order_by('_dateCreated', direction=firestore.firestore.Query.DESCENDING).limit(1).get()
            result['refresh_token'] = r[0].to_dict().get('_authResponse', {}).get('refresh_token', '')
            result['document_id'] = r[0].to_dict().get('_authResponse', {}).get('state', '')
            result['_nyhaValue'] = r[0].to_dict().get('_nyhaValue', None)
        except BaseException as e:
            print(f"Error in get_user_latest_refresh_token: {sys.exc_info()}")
            raise e

        return result

    def get_client_secret_from_sites(self, site):

        try:
            r = self.db.collection('sites').document(site).get()
            # if settings.DB_SITE != 'local' or site == 'sandbox' or :
            result = r.to_dict()['clientSecret']
            # else:
            #     result = r.to_dict()['clientSecretDev']
        except BaseException as e:
            print(f"Error in get_client_secret_from_sites: {sys.exc_info()}")
            raise e

        return result

    # def get_filtered_documents_from_collection_multiple_query(self, collection_name, field_name1, field_value1, field_name2, field_value2):
    #     result = []
    #     try:
    #         doc_list = self.db.collection(collection_name).where(field_name1, u'==', field_value1).where(field_name2, u'==', field_value2).get() #
    #         if len(doc_list) > 0:
    #             for item in doc_list:
    #                 if 'dateRandomized' in item.to_dict():
    #                     user = {'userId': item.to_dict()['userId'], 'dateRandomized': item.to_dict()['dateRandomized']}
    #                 else:
    #                     user = {'userId': item.to_dict()['userId'], 'dateRandomized': datetime.datetime.now()}
    #                 result.append(user)
    #     except BaseException as e:
    #         print(f"Error in get_filtered_documents_from_collection: {sys.exc_info()}")
    #         raise e
    #
    #     return result
    #
    # def get_filtered_documents_from_subcollection_multiple_query(self, collection_name, field_name1, field_value1, field_name2, field_value2):
    #     result = []
    #     try:
    #         doc_list = self.db.collection(collection_name).where(field_name1, u'==', field_value1).where(field_name2, u'==', field_value2).get() #
    #         if len(doc_list) > 0:
    #             for item in doc_list:
    #                 result.append(item.to_dict()['userId'])
    #     except BaseException as e:
    #         print(f"Error in get_filtered_documents_from_collection: {sys.exc_info()}")
    #         raise e
    #
    #     return result
    #
    # def get_documents_from_subcollection(self, collection_name, document_id, subcollection_name, order_by):
    #     result = []
    #
    #     try:
    #         collection_list = self.db.collection(collection_name).document(document_id).collection(subcollection_name)\
    #             .order_by(order_by, direction=firestore.firestore.Query.ASCENDING).get()
    #         if len(collection_list) > 0:
    #             for item in collection_list:
    #                 result.append(item.to_dict())
    #
    #     except BaseException as e:
    #         print(f"Error in get_documents_from_subcollection: {sys.exc_info()}")
    #         raise e
    #
    #     return result
    #
    # def get_latest_document_from_subcollection(self, collection_name, document_id, subcollection_name):
    #     result = {}
    #
    #     try:
    #         collection_list = self.db.collection(collection_name).document(document_id).collection(subcollection_name) \
    #             .order_by('dateCreated', direction=firestore.firestore.Query.DESCENDING).limit(1).get()
    #         if len(collection_list) > 0:
    #             result: dict = collection_list[0].to_dict()
    #
    #     except BaseException as e:
    #         print(f"Error in get_latest_document_from_subcollection: {sys.exc_info()}")
    #         raise e
    #
    #     return result
    #
    # def get_latest_document_from_subcollection_filtered_ordered_by_field(self, collection_name, document_id, subcollection_name, field_name, field_value, order_field_name):
    #     result = []
    #
    #     try:
    #         collection_list = self.db.collection(collection_name).document(document_id).collection(subcollection_name) \
    #             .where(field_name, u'==', field_value) \
    #             .order_by(order_field_name, direction=firestore.firestore.Query.ASCENDING).get()
    #         if len(collection_list) > 0:
    #             for item in collection_list:
    #                 result.append(item.to_dict())
    #
    #     except BaseException as e:
    #         print(f"Error in get_latest_document_from_subcollection_filtered_ordered_by_field: {sys.exc_info()}")
    #         raise e
    #
    #     return result

    def saveInterventionToFirestore(self, document_id, data):
        result = ""
        if datetime.now() == datetime.utcnow():
            date = (datetime.now() - timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%S")
        else:
            date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        try:
            result = self.db.collection("users").document(document_id).collection("interventions").document(date).set(data)
        except Exception as e:
            print("Error saving FHIRdata to Firestore:")
            print(e)
        return result

    # def save_to_collection(self, collection_name, data):
    #     result = []
    #
    #     try:
    #         result = self.db.collection(collection_name).add(data)
    #     except BaseException as e:
    #         print(f"Error in save_to_collection: {sys.exc_info()}")
    #         raise e
    #
    #     return result
    #
    # def save_to_sub_collection(self, collection_name, document_name, sub_collection_name, data):
    #     result = []
    #
    #     try:
    #         result = self.db.collection(collection_name).document(document_name).collection(sub_collection_name).add(data)
    #
    #     except BaseException as e:
    #         print(f"Error in save_to_sub_collection: {sys.exc_info()}")
    #         raise e
    #
    #     return result

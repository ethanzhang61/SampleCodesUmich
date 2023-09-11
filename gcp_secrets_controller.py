import os
from google.cloud import secretmanager
import settings as st

if st.DB_SITE == "local-dev":
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "smarthfdev-740d1e47376b-secrets.json"
elif st.DB_SITE == "local-prod":
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "smarthfprod-sa.json"
class GcpSecretsController:

    def __init__(self, project_id):
        self.project_id = project_id

    def access_secret_version(self, secret_id, version_id):
        """
        Access the payload for the given secret version if one exists. The version
        can be a version number as a string (e.g. "5") or an alias (e.g. "latest").
        """

        payload = b''

        print("running access_secret_version")
        try:
            # Create the Secret Manager client.
            client = secretmanager.SecretManagerServiceClient()

            # Build the resource secret_name of the secret version.
            secret_name = f"projects/{self.project_id}/secrets/{secret_id}/versions/{version_id}"
            # Access the secret version.
            # WARNING: Do not print the secret in a production environment - this
            # snippet is showing how to access the secret material.
            response = client.access_secret_version(request={"name": secret_name})
            payload_hex_bytes = response.payload.data
            payload_hex_str = payload_hex_bytes.decode('utf-8')
            payload = bytes.fromhex(payload_hex_str)
        except Exception as e:
            print(f"Error in access_secret_version: {e}")

        return payload

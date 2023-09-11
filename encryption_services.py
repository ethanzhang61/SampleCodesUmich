import base64
import logging.config
import os
import dateutil.parser
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
import gcp_secrets_controller as gcpsc
import settings as st
import binascii


# logging.config.fileConfig('logging.conf')
# logger = logging.getLogger('simple')


class EncryptionServices:

    def __init__(self):
        if st.DB_SITE == "local-dev":
            project_id = "smarthfdev"
        elif st.DB_SITE == "local-prod":
            project_id = "smarthfprod"
        else:
            project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', None)
        self.public_key = self.get_public_key()
        gcp_secrets_controller = gcpsc.GcpSecretsController(project_id)
        private_key_str = gcp_secrets_controller.access_secret_version('private_key_hex', 1)
        self.private_key = RSA.import_key(private_key_str)

    def get_public_key(self):
        pem_bytes = binascii.unhexlify(st.publicKeyHex)
        pem_string = pem_bytes.decode('utf-8')
        public_key = RSA.import_key(pem_string).publickey()
        return public_key

    def encrypt_string(self, string_to_encrypt):
        result = ""
        try:
            split_string = string_to_encrypt.split("_")
            if split_string[0] == "encrypted":
                result = string_to_encrypt
            else:
                data_to_encrypt = string_to_encrypt.encode('utf-8')
                encrypted_bytes = self.rsa_encrypt(data_to_encrypt)
                base64_encoded = base64.b64encode(encrypted_bytes).decode('utf-8')
                result = f"encrypted_{base64_encoded}"
        except Exception as e:
            result = "could_not_encrypt"
            logging.error(e)

        return result

    def rsa_encrypt(self, data_to_encrypt):
        encryptor = PKCS1_OAEP.new(self.public_key)
        max_chunk_size = self.public_key.size_in_bytes() - 42 #(self.public_key.size_in_bytes() + 7) // 8 - 42
        encrypted_chunks = []

        for i in range(0, len(data_to_encrypt), max_chunk_size):
            chunk_size = min(max_chunk_size, len(data_to_encrypt) - i)
            chunk = data_to_encrypt[i:i + chunk_size]
            encrypted_chunk = encryptor.encrypt(chunk)
            encrypted_chunks.append(encrypted_chunk)

        return b''.join(encrypted_chunks)

    def encrypt_complex_map(self, resource):
        try:
            for key in resource.keys():
                value = resource[key]
                if isinstance(value, dict):
                    resource[key] = self.encrypt_complex_map(value)
                elif isinstance(value, list):
                    for i in range(len(value)):
                        if isinstance(value[i], dict):
                            value[i] = self.encrypt_complex_map(value[i])
                elif isinstance(value, str):
                    resource[key] = self.encrypt_string(value)
        except Exception as e:
            resource = {"result": "could_not_encrypt"}
            logging.error(e)

        return resource

    def decrypt_dict(self, encrypted_dict):
        result = {}
        try:
            for key, value in encrypted_dict.items():
                converted_value = ""

                if type(value) is str:
                    split_value = value.split("_")
                    if self.is_encrypted(split_value[0]):
                        decrypted_value = self.decrypt(split_value[1])
                        if self.is_iso_datetime(decrypted_value):
                            # Convert the ISO 8601 string to a Python datetime object
                            converted_value = dateutil.parser.isoparse(decrypted_value)
                        else:
                            converted_value = decrypted_value

                    else:
                        converted_value = split_value[0]
                else:
                    converted_value = value
                result[key] = converted_value

        except Exception as e:
            print(e)

        return result

    def is_encrypted(self, string_to_check):
        result = False

        trimmed_string = string_to_check.split("_")
        if trimmed_string[0] == "encrypted":
            result = True

        return result

    def decrypt(self, encrypted_str):
        result = ""

        try:
            # Decode the base64-encoded string to a byte string
            encrypted_bytes = base64.b64decode(encrypted_str.encode('utf-8'))
            decrypted_message = self.rsa_decrypt(encrypted_bytes)
            # print('Decrypted message:', decrypted_message.decode('utf-8'))
            # Decode the decrypted byte string to a UTF-8 string
            result = decrypted_message.decode('utf-8')

        except Exception as e:
            print(e)
            print(encrypted_str)

        return result

    def is_iso_datetime(self, s):
        try:
            dateutil.parser.isoparse(s)
            return True
        except ValueError:
            return False

    def rsa_decrypt(self, data_to_decrypt):
        decryptor = PKCS1_OAEP.new(self.private_key)
        chunk_size = self.private_key.size_in_bytes()
        decrypted_chunks = []

        for i in range(0, len(data_to_decrypt), chunk_size):
            chunk = data_to_decrypt[i:i + chunk_size]
            decrypted_chunks.append(decryptor.decrypt(chunk))
        return b''.join(decrypted_chunks)

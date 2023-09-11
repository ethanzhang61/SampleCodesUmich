import requests
import json
import base64

import encryption_services
import settings as st
import standards
import endpoints
import resources
import parser_services as ps
import re
import globals
# import data.rx_terms_ingredients as rx
import data.rx_data as rx_data
import data.hf_medications as hf_medications
from encryption_services import EncryptionServices

class fhir_controller:
    encryption_services = EncryptionServices()
    user_nyha_value = 0
    authResponse = {}
    access_token = ''
    user = {}
    def __init__(self, user, FireStoreService):

        self.user = user
        self.parser = ps.MedOptParser(user)
        # first_intervention = FireStoreService.get_user_latest_manual_intervention(user['document_id'])
        # decrypted_first_intervention = self.encryption_services.decrypt_dict(first_intervention)
        refresh_token = user['refresh_token']
        self.user_nyha_value = user['_nyhaValue']
        print(f"Refresh token is: {refresh_token}")
        client_secret = FireStoreService.get_client_secret_from_sites(user['site'])
        print(f"client Secret is: {client_secret}")

        endpoint = list(filter(lambda e: e['OrganizationId'] == user['site'], endpoints.endpointsList))
        client_id = endpoint[0]['ClientId']
        access_token_url = f"https://{endpoint[0]['FHIRHost']}{endpoint[0]['FHIRPatientFacingPath']}/oauth2/token"
        print(f"Client ID: {client_id}, secret: {client_secret} access_token_url: {access_token_url}")

        auth = (base64.b64encode((client_id + ':' + client_secret).encode("ascii"))).decode("ascii")
        data = {'grant_type': 'refresh_token', 'refresh_token': refresh_token}
        headers = {'Authorization': f'Basic {auth}',
                   'Content-Type': 'application/x-www-form-urlencoded'}

        response = requests.post(url=access_token_url, headers=headers, data=data)
        # Check if the request was successful
        if response.status_code == 200:
            # Parse the response JSON data
            token_data = json.loads(response.text)
            self.authResponse = token_data
            # Extract the new access token
            self.access_token = token_data.get('access_token')
            # Print the new access token
            print(f'New Access Token for user {user["_epicId"]}: {self.access_token}')
        else:
            # Print an error message if the request was not successful
            print(f'Error for user {user["_epicId"]}: {response.status_code} - {response.reason}')

    def createFHIRURL(self, resource):
        user_epicId = self.user['_epicId']
        FHIRFinalURL = ''
        for endpoint in endpoints.endpointsList:
            if endpoint['OrganizationId'] == self.user['site']:
                FHIRFinalURL += endpoint['FHIRBaseURL']

        if resource == 'Medication':
            return FHIRFinalURL
        else:
            match len(resources.resourcesList[resource]['filters']):
                case 0:
                    return f"{FHIRFinalURL}/{resources.resourcesList[resource]['resourceUrl']}/{user_epicId}"
                case 1:
                    return f"{FHIRFinalURL}/{resources.resourcesList[resource]['resourceUrl']}?patient={user_epicId}"
                case 2:
                    parameter_name = ''
                    parameter_value = ''
                    for filter in resources.resourcesList[resource]['filters']:
                        if filter['name'] != 'patient':
                            parameter_name = filter['name']
                            parameter_value = filter['value']
                    return f"{FHIRFinalURL}/{resources.resourcesList[resource]['resourceUrl']}?patient={user_epicId}&{parameter_name}={parameter_value}"

    def getFHIRResponse(self, FHIRFinalURL, category):
        try:
            fhir_authorization = {'Accept': 'application/fhir+json', 'Authorization': f'Bearer {self.access_token}'}
            response = requests.get(url=FHIRFinalURL, headers=fhir_authorization)
            if response.status_code == 200:
                # Parse the response JSON data
                FHIRdata = json.loads(response.text)
                return FHIRdata
            else:
                # Print an error message if the request was not successful
                print(f'Error in {category}: {response.status_code} - {response.reason}')
        except Exception as e:
            print("Fail to get access token or form valid FHIR url:")
            print(e)

    def getVitals(self):
        results = {}
        try:
            FHIRFinalURL = self.createFHIRURL('vitals')
            response = self.getFHIRResponse(FHIRFinalURL, 'vitals')
            results = self.parser.parseVitals(response)
        except Exception as e:
            print("Error getting Vitals from FHIR:")
            print(e)
        return results

    def getEjectionFraction(self):
        results = {}
        try:
            FHIRFinalURL = self.createFHIRURL('observationsEjectionFraction')
            response = self.getFHIRResponse(FHIRFinalURL, 'EjectionFraction')
            results = self.parser.parseEjectionFraction(response)
        except Exception as e:
            print("Error getting EjectionFraction from FHIR:")
            print(e)
        return results

    def getEGFR(self):
        results = {'eGFRFromFhir': {}, 'eGFRForMedOpt': {}, 'eGFRForBackend': {}}
        try:
            FHIRFinalURL = self.createFHIRURL('observationsEGFR')
            response = self.getFHIRResponse(FHIRFinalURL, 'EGFR')
            parsed_result = self.parser.parseEGFR(response)
            results['eGFRFromFhir'] = response
            results['eGFRForMedOpt'] = parsed_result
        except Exception as e:
            print("Error getting eGFR from FHIR:")
            print(e)
        return results

    def getCreatinine(self):
        results = {'creatinineFromFhir': {}, 'creatinineForMedOpt': {}, 'creatinineForBackend': {}}
        try:
            FHIRFinalURL = self.createFHIRURL('creatinine')
            response = self.getFHIRResponse(FHIRFinalURL, 'Creatinine')
            parsed_result = self.parser.parseCreatinine(response)
            results['creatinineFromFhir'] = response
            results['creatinineForMedOpt'] = parsed_result
        except Exception as e:
            print("Error getting Creatinine from FHIR:")
            print(e)
        return results

    def getPotassium(self):
        results = {'potassiumFromFhir': {}, 'potassiumForMedOpt': {}, 'potassiumForBackend': {}}
        try:
            FHIRFinalURL = self.createFHIRURL('potassium')
            response = self.getFHIRResponse(FHIRFinalURL, 'Potassium')
            parsed_result = self.parser.parsePotassium(response)
            results['potassiumFromFhir'] = response
            results['potassiumForMedOpt'] = parsed_result
        except Exception as e:
            print("Error getting Potassium from FHIR:")
            print(e)
        return results

    def getPatient(self):
        results = {'patientFromFhir': {}, 'patientForBackend': {}}
        try:
            FHIRFinalURL = self.createFHIRURL('patient')
            response = self.getFHIRResponse(FHIRFinalURL, 'patient')
            parsed_result = self.parser.parsePatient(response)
            results['patientFromFhir'] = response
            results['patientForBackend'] = parsed_result
        except Exception as e:
            print("Error getting Patient from FHIR:")
            print(e)
        return results

    def getAllergies(self):
        results = {'allergiesFromFhir': {}, 'allergiesForMedOpt': [], 'allergiesForBackend': {}}
        try:
            FHIRFinalURL = self.createFHIRURL('allergies')
            response = self.getFHIRResponse(FHIRFinalURL, 'allergies')
            parsed_result = self.parser.parseAllergies(response)
            results['allergiesFromFhir'] = response
            results['allergiesForMedOpt'] = parsed_result
            results['allergiesForBackend'] = parsed_result

        except Exception as e:
            print("Error getting Allergies from FHIR:")
            print(e)
        return results

    def getMedications(self):
        results = {'medicationsFromFhir': {}, 'medicationsForMedOpt': [], 'medicationsForBackend': {}}
        try:
            FHIRFinalURL = self.createFHIRURL('medicationRequestOrders')
            response = self.getFHIRResponse(FHIRFinalURL, 'Medications')
            parsed_result = self.parser.parseMedications(response)
            results['medicationsFromFhir'] = response

            medicationsForMedOpt = []
            for medicationRequest in parsed_result:
                medications_for_med_opt = self.processMedication(medicationRequest)
                medicationsForMedOpt.extend(medications_for_med_opt)

            results['medicationsForMedOpt'] = medicationsForMedOpt
            results['medicationsForBackend'] = medicationsForMedOpt
        except Exception as e:
            print("Error getting Medications from FHIR:")
            print(e)
        return results

    def processMedication(self, medicationRequest):
        medications_for_med_opt = []

        try:
            # Get medicationResource from FHIR
            medication_resource = self.getMedicationsFromRequest(medicationRequest)
            # This is the code that we will compare later to get the ingredients from the table
            clinical_product_coding = self.extract_clinical_product_coding(medication_resource)
            if clinical_product_coding:
                # Get ingredients from the CodeRx RxNorm Table
                ingredientsFromRxNormTable = self.getIngredientsFromRxNormTable(clinical_product_coding)
                # print(ingredientsFromRxNormTable)
                if ingredientsFromRxNormTable:
                    for ingredientFromRxNormTable in ingredientsFromRxNormTable:
                        ingredientFromHFMedicationsTable = self.getIngredientFromHFMedicationsTable(ingredientFromRxNormTable)
                        print(ingredientFromHFMedicationsTable)
                        if ingredientFromHFMedicationsTable:
                            ingredientName = ingredientFromHFMedicationsTable.get('ingredientName', '')
                            ingredientRxcui = ingredientFromHFMedicationsTable.get('ingredientRxcui', '')
                            daily_dose = self.getDailyDose(ingredientFromRxNormTable, medicationRequest, ingredientFromHFMedicationsTable)

                        # TODO: If the ingredient name is compounded, then we can replace the space with an underscore? As in
                        # TODO: metoprolol_tartrate.
                        #     ingredient_component_name = str(ingredientFromRxNormTable['ingredient_component_name'])
                        #     ingredient_component_rxcui = str(ingredientFromRxNormTable['ingredient_component_rxcui'])

                            medication = {}
                            medication['name'] = ingredientName
                            medication['rxcui'] = ingredientRxcui
                            medication['dose'] = daily_dose
                            medications_for_med_opt.append(medication)
                            print(f"medication: {medication}")
        except Exception as e:
            print("Error in processMedication")
            print(e)

        return medications_for_med_opt

    def getIngredientFromHFMedicationsTable(self, ingredientFromRxNormTable):
        ingredientFromHFMedicationsTable = {}

        try:
            for key, value in ingredientFromRxNormTable.items():
                if value == "NULL":
                    ingredientFromRxNormTable[key] = ""

            ingredientComponentName = str(ingredientFromRxNormTable['ingredient_component_name'])
            preciseIngredientName = str(ingredientFromRxNormTable['precise_ingredient_name'])

            for hfMedicationsTableRow in hf_medications.hf_medications:
                for key, value in hfMedicationsTableRow.items():
                    if value == "NULL":
                        hfMedicationsTableRow[key] = ""

                hfMedsIngredientComponentName = str(hfMedicationsTableRow['ingredient_component_name'])
                hfMedsIngredientComponentRxcui = str(hfMedicationsTableRow['ingredient_component_rxcui'])
                hfMedsPreciseIngredientName = str(hfMedicationsTableRow['precise_ingredient_name'])
                hfMedsPreciseIngredientRxcui = str(hfMedicationsTableRow['precise_ingredient_rxcui'])
                hfMedsAlgorithmName = str(hfMedicationsTableRow['algorithm_name'])
                hfMedsFrequency = hfMedicationsTableRow.get('frequency', 1)
                hfMedsPeriod = hfMedicationsTableRow.get('period', 1)
                hfMedsPeriodUnit = str(hfMedicationsTableRow.get('period_unit', ''))

                if ingredientComponentName == hfMedsIngredientComponentName and preciseIngredientName == hfMedsPreciseIngredientName:
                    ingredientFromHFMedicationsTable = {
                        "ingredientName": hfMedsAlgorithmName,
                        "frequency": hfMedsFrequency,
                        "period": hfMedsPeriod,
                        "periodUnit": hfMedsPeriodUnit,
                    }

                    if hfMedsPreciseIngredientName == "":
                        ingredientFromHFMedicationsTable['ingredientRxcui'] = hfMedsIngredientComponentRxcui
                    elif hfMedsPreciseIngredientName != "":
                        ingredientFromHFMedicationsTable['ingredientRxcui'] = hfMedsPreciseIngredientRxcui

        except Exception as e:
            print(e)

        # print(f"ingredientFromHFMedicationsTable: {ingredientFromHFMedicationsTable}")

        return ingredientFromHFMedicationsTable

    def getDailyDose(self, ingredientFromRxNormTable, medicationRequest, ingredientFromHFMedicationsTable):
        dailyDose = 0.0
        dose = 0.0
        doseQuantity = {}

        try:
            # First try getting doseQuantity from MedicationRequest
            doseQuantity = self.getDoseQuantityFromMedicationRequest(medicationRequest)

            # Todo: Then try getting doseQuantity from Language Model
            # if (doseQuantity.isEmpty) {
            #   getDoseQuantityFromLanguageModel();
            # }

            # Finally try getting doseQuantity from default
            if not doseQuantity:
                # Todo: Set to right default values, maybe take it out from the table?
                doseQuantity['value'] = 1
                doseQuantity['unit'] = "tablet"

            # Get strength information from the CodeRx RxNorm table
            strengthNumeratorValue = ingredientFromRxNormTable.get('strength_numerator_value', 0.0)
            strengthNumeratorUnit = (ingredientFromRxNormTable.get('strength_numerator_unit', "")).lower()

            doseValue = doseQuantity.get('value', 0.0)
            doseUnit = (doseQuantity.get('unit', "")).lower()

            # print(doseQuantity)
            if doseValue != 0 and doseUnit == strengthNumeratorUnit:
                dose = doseValue

            # Check that doseUnit exists.
            if strengthNumeratorValue != 0 and doseValue != 0 and doseUnit != strengthNumeratorUnit:
                dose = strengthNumeratorValue * doseValue
            # Get timing
            timing = self.getTiming(ingredientFromRxNormTable, medicationRequest, ingredientFromHFMedicationsTable)
            timing.calculate_daily_amount()

            dailyDose = dose * timing.daily_amount
        except Exception as e:
            print(e)

        return dailyDose

    def getTiming(self, ingredientFromRxNormTable, medicationRequest, ingredientFromHFMedicationsTable):
        timing = Timing()
        try:
            # First try getting the timing directly from MedicationRequest.
            # The frequency and period are mostly not available in MedicationRequest, but we should try to get it anyway.
            timing = self.getTimingFromMedicationRequest(medicationRequest)

            # Todo:Then try to get the timing from Language Model
            # If we have a string that provides some instruction
            # if (timing.isEmpty()) {
            #   getTimingFromLanguageModel();
            # }
            # Then set the timing from defaults. This is not accurate. Should only be used as a last resort.
            if timing.is_empty():
                timing.frequency = 1
                timing.period = 1
                timing.period_unit = "d"

            # Then get the timing from Mike's table.
            if timing.is_empty():
                # timing = self.getTimingFromHFMedicationsTable(ingredientFromTable)
                timing.frequency = ingredientFromHFMedicationsTable.get('frequency', 1)
                timing.period = ingredientFromHFMedicationsTable.get('period', 1)
                timing.period_unit = ingredientFromHFMedicationsTable.get('periodUnit', 'd')
        except Exception as e:
            print(e)

        return timing

    def getTimingFromHFMedicationsTable(self, ingredientFromTable):
        timing = Timing()
        try:

            hfMedicationsList = hf_medications.hf_medications

            ingredientName = ingredientFromTable['ingredient_name']
            ingredientNamesList = re.split(r'\s*/\s*', ingredientName)

            for item in hfMedicationsList:
                if any(name in item['name'] for name in ingredientNamesList):
                    timing.frequency = item['frequency'] or 1
                    timing.period = item['period'] or 1
                    timing.periodUnit = str(item['period_unit'] or "")
                    # logger.d(f"frequency: {timing.frequency}, period: {timing.period}, periodUnit: {timing.periodUnit}")
                    break
        except Exception as e:
            print(e)

        return timing

    def getTimingFromMedicationRequest(self, medicationRequest):
        # The frequency and period are mostly not available in MedicationRequest, but we should try to get it anyway.
        timing = Timing()
        try:
            dosageInstruction = medicationRequest.get('dosageInstruction', [])

            if dosageInstruction:
                timingResource = dosageInstruction[0].get('timing', {})

                if timingResource:
                    timing.frequency = timingResource.get('frequency', 0)
                    timing.period = timingResource.get('period', 0)
                    timing.periodUnit = timingResource.get('periodUnit', "")
        except Exception as e:
            print(e)

        return timing

    def getDoseQuantityFromMedicationRequest(self, medicationRequest):
        doseQuantity = {}
        doseAndRateFirst = {}
        # print(medicationRequest)
        try:
            dosageInstruction = medicationRequest.get('dosageInstruction', [])

            if dosageInstruction:
                dosageInstructionFirst = dosageInstruction[0]
                if dosageInstructionFirst:
                    doseAndRate = dosageInstructionFirst.get('doseAndRate', [])
                    # print(f"doseAndRate: {doseAndRate}")
                    if doseAndRate:
                        doseAndRateFirst = doseAndRate[0]
                        if doseAndRateFirst:
                            doseQuantity = doseAndRateFirst.get('doseQuantity', {})
        except Exception as e:
            print(e)

        # print(f"doseQuantity: {doseQuantity}")
        return doseQuantity

    def getIngredientsFromRxNormTable(self, clinical_product_coding):
        ingredients_from_table = []

        try:
            for code_map in clinical_product_coding:
                system = code_map.get('system', '')
                if system == 'http://www.nlm.nih.gov/research/umls/rxnorm':
                    code = code_map.get('code', '')
                    if code:
                        ingredients_for_code = self.extract_ingredients_from_rx_norm_data(code)
                        ingredients_from_table.extend(ingredients_for_code)
        except Exception as e:
            print(e)

        return ingredients_from_table

    def extract_ingredients_from_rx_norm_data(self, code):
        result = []

        try:
            for item in rx_data.rx_data:
                clinical_product_rxcui = str(item.get('clinical_product_rxcui', ''))
                if clinical_product_rxcui == code:
                    result.append(item)
        except Exception as e:
            print(e)

        return result

    def extract_clinical_product_coding(self, medication_resource):
        coding = []

        try:
            code = medication_resource.get('code', {})
            coding = code.get('coding', [])

            if not coding:
                coding = self.extract_ingredient_coding(medication_resource)
        except Exception as e:
            print(e)

        return coding

    def extract_ingredient_coding(self, medication_resource):
        ingredient_coding = []

        try:
            ingredient = medication_resource.get('ingredient', [])
            if ingredient:
                ingredient_first = ingredient[0] or {}
                item_codeable_concept = ingredient_first.get('itemCodeableConcept', {})
                ingredient_coding = item_codeable_concept.get('coding', [])
        except Exception as e:
            print(e)

        return ingredient_coding

    def getMedicationsFromRequest(self, medicationRequest):
        result = {}
        try:
            medicationReference = medicationRequest.get("reference", {})
            FHIRFinalURL = f"{self.createFHIRURL('Medication')}/{medicationReference}"
            result = self.getFHIRResponse(FHIRFinalURL, 'Medication')
        except Exception as e:
            print("Error getting Medications Reference from FHIR:")
            print(e)
        return result

    def formFHIRdata(self):
        result = {
            'allergies': {},
            'creatinine': {},
            'eGFR': {},
            'medications': {},
            'patient': {},
            'potassium': {},
            'vitals': {},
            'observationsEchocardiogram': {},
            'observationsEjectionFraction': {},
            'observationsLabs': {},
            'observationsVitals': {},
            'diagnosticReport': {},
            'labs': {},
            'nyha_class': "",
            '_authStatus': False
        }
        # return Formed FHIR data ready to send to MedOpt and save to DB
        if self.access_token != '':
            result['allergies'] = self.getAllergies()
            self.encryption_services.encrypt_complex_map(resource=result['allergies']['allergiesFromFhir'])
            result['creatinine'] = self.getCreatinine()
            self.encryption_services.encrypt_complex_map(resource=result['creatinine']['creatinineFromFhir'])
            result['potassium'] = self.getPotassium()
            self.encryption_services.encrypt_complex_map(resource=result['potassium']['potassiumFromFhir'])
            result['eGFR'] = self.getEGFR()
            self.encryption_services.encrypt_complex_map(resource=result['eGFR']['eGFRFromFhir'])
            result['medications'] = self.getMedications()
            self.encryption_services.encrypt_complex_map(resource=result['medications']['medicationsFromFhir'])
            result['observationsEjectionFraction'] = self.getEjectionFraction()
            self.encryption_services.encrypt_complex_map(resource=result['observationsEjectionFraction'])
            result['patient'] = self.getPatient()
            self.encryption_services.encrypt_complex_map(resource=result['patient'])
            result['vitals'] = self.getVitals()
            result['nyha_class'] = self.user_nyha_value
            result['_authStatus'] = True
        else:
            print("No access token.")
        return result

class Timing:
    def __init__(self, frequency=0, period=0, period_unit=""):
        self.frequency = int(frequency) if isinstance(frequency, int) else int(frequency or 0)
        self.period = int(period) if isinstance(period, int) else int(period or 0)
        self.period_unit = period_unit
        self.period_units_table = {"d": 1, "h": 24}
        self.daily_amount = 0.0

    def is_empty(self):
        return self.frequency == 0 or self.period == 0 or not self.period_unit

    def calculate_daily_amount(self):
        try:
            daily_period_multiplier = self.period_units_table.get(self.period_unit, 0)
            self.daily_amount = self.frequency * self.period / daily_period_multiplier
        except Exception as e:
            print(e)

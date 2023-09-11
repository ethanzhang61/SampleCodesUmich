import datetime
import re

import standards


class MedOptParser:
    def __init__(self, user):
        self.user = user
    def getCodes(self, coding):
        result = []
        try:
            for item in coding:
                result.append(item['code'])
        except Exception as e:
            print("Error getCodes:")
            print(e)
        return result

    def returnValueIfExists(self, m, k):
        result = ""
        try:
            if k in m:
                result = str(m[k])
        except Exception as e:
            print("Error returning value if exists:")
            print(e)
        return result

    def getDaysPassed(self, lastBpDateTime):
        daysPassed = 0
        try:
            now = datetime.datetime.now()
            daysPassed = (now - lastBpDateTime).days
        except Exception as e:
            print("Error getting days passed:")
            print(e)
        return daysPassed

    def parsePatient(self, response):
        age = ''
        firstName = ''
        lastName = ''
        phone = ''
        state = ''
        is_african_american = False
        try:
            birthDate = datetime.datetime.strptime(response['birthDate'], '%Y-%m-%d').date()
            age = datetime.datetime.today().year - birthDate.year - \
                  ((datetime.datetime.today().month, datetime.datetime.today().day) < (birthDate.month, birthDate.day))
        except Exception as e:
            print("Error getting age:")
            print(e)
        try:
            names = response.get('name', [])
            for name in names:
                if name['use'] == 'usual':
                    firstName = name.get('given', [])[0]
                    lastName = name.get('family', '')
        except Exception as e:
            print("Error getting first or last name:")
            print(e)
        try:
            telecoms = response.get('telecom', [])
            for telecom in telecoms:
                if telecom.get('use', '') == 'home':
                    phone = telecom['value']
        except Exception as e:
            print("Error getting phone number")
            print(e)
        try:
            addresses = response.get('address', [])
            for address in addresses:
                if address['use'] == 'home':
                    state = address['state']
        except Exception as e:
            print("Error getting state in address")
            print(e)
        try:
            extension = response.get('extension', [])
            for entry in extension:
                if entry['url'] == 'http://hl7.org/fhir/us/core/StructureDefinition/us-core-race':
                    for ext in entry['extension']:
                        if 'valueCoding' in ext:
                            if ext['valueCoding']['code'] in standards.kAfricanAmericanCodes:
                                is_african_american = True
        except Exception as e:
            print("Error getting race")
            print(e)
        result = {
            'age': age,
            'email': self.user['_email'] or '',
            'firstName': firstName,
            'gender': response['gender'],
            'id': response['id'],
            'lastName': lastName,
            'phone': phone,
            'state': state,
            'is_african_american': is_african_american,
        }
        return result

    def parseMedications(self, response):
        results = []
        entries = response['entry']
        try:
            for entry in entries:
                try:
                    medication = {}
                    resource = entry.get('resource', {})
                    resourceType = resource.get('resourceType', '')
                    if resourceType == 'MedicationRequest':
                        medicationReference = resource.get('medicationReference', {})
                        medication['reference'] = medicationReference.get('reference', [])
                        medication['text'] = medicationReference.get('display', [])
                        medication['dosageInstructions'] = resource.get('dosageInstruction', {})
                        results.append(medication)
                except Exception as e:
                    print("Error parsing a medication:")
                    print(e)
        except Exception as e:
            print("Error in parseMedicationRequests:")
            print(e)
        return results

    def parseEjectionFraction(self, response):
        return response

    def parseEGFR(self, response):
        result = {}

        try:
            if response.get('entry'):
                entries = response['entry']
                newEntries = []
                for entry in entries:
                    resource = entry.get('resource')
                    if resource:
                        effectiveDateTime = resource.get('effectiveDateTime')
                        valueQuantity = resource.get('valueQuantity')
                        if valueQuantity and effectiveDateTime and effectiveDateTime.strip():
                            eGFRValue = valueQuantity.get('value', '')
                            eGFRUnit = valueQuantity.get('unit', '')
                            newEntries.append({
                                "unit": eGFRUnit,
                                "value": eGFRValue,
                                "effectiveDateTime": effectiveDateTime
                            })
                            # print(f"eGFR: {eGFRValue} {eGFRUnit}")

                if newEntries:
                    # Filter the list based on the conditions
                    filteredList = list(filter(lambda map: map['value'] and map['value'] > 0, newEntries))

                    # Find the newest map
                    dateFormat = '%Y-%m-%dT%H:%M:%SZ'
                    result = max(filteredList, key=lambda map: datetime.datetime.strptime(map['effectiveDateTime'], dateFormat))
        except Exception as e:
            print(e)

        return result

    def parseVitals(self, response):
        vitals = {}
        try:
            entries = response['entry']
            lastBpDateTime = datetime.datetime(1900, 1, 1, 0, 0, 0)
            lastHrDateTime = datetime.datetime(1900, 1, 1, 0, 0, 0)
            for entry in entries:
                entryResource = entry.get('resource', {})
                entryResourceType = entryResource.get('resourceType', "")
                if entryResourceType == 'Observation':
                    resource = entry.get('resource', {})
                    resourceCode = resource.get('code', {})
                    resourceCoding = resourceCode.get('coding', [])
                    vitalCodes = self.getCodes(resourceCoding) or []
                    if standards.bpCode in vitalCodes:
                        components = resource.get('component', [])
                        for component in components:
                            componentCode = component.get('code', {})
                            componentCoding = componentCode.get('coding', [])
                            componentTypes = self.getCodes(componentCoding) or []
                            if standards.sbpCode in componentTypes:
                                thisBpDateTime = datetime.datetime.strptime(self.returnValueIfExists(resource, 'effectiveDateTime'), '%Y-%m-%dT%H:%M:%SZ')
                                if thisBpDateTime > lastBpDateTime:
                                    lastBpDateTime = thisBpDateTime
                                    vitals["sbp"] = component['valueQuantity']['value']
                                    vitals["sbpDaysPassed"] = self.getDaysPassed(lastBpDateTime)
                    elif standards.hrCode in vitalCodes:
                        thisHrDateTime = datetime.datetime.strptime(self.returnValueIfExists(resource, 'effectiveDateTime'), '%Y-%m-%dT%H:%M:%SZ')
                        if thisHrDateTime > lastHrDateTime:
                            lastHrDateTime = thisHrDateTime
                            vitals['hr'] = resource['valueQuantity']['value']
                            vitals["hrDaysPassed"] = self.getDaysPassed(lastHrDateTime)
        except Exception as e:
            print("Error parsing vitals:")
            print(e)
        return vitals

    def parseAllergies(self, response):
        allergies = []
        try:
            entries = response.get('entry', [])
            for entry in entries:
                resource = entry.get('resource', {})
                code = resource.get('code', {})
                name = code.get('text', '')
                coding = code.get('coding', [])
                codingItem = {} if len(coding) == 0 else coding[0]
                codeValue = codingItem.get('code', '')
                codeType = codingItem.get('system', '')
                if len(name) > 0  and len(codeValue) > 0 and len(codeType) > 0:
                    nameReplaced = re.sub(r'[\/\-\s]+', "_", name)
                    nameLowerCase = nameReplaced.lower()
                    allergies.append(nameLowerCase)
        except Exception as e:
            print("Error parsing Allergies:")
            print(e)
        return allergies

    def parsePotassium(self, response):
        results = {}
        try:
            callResponse = []
            entries = response.get('entry', [])
            for entry in entries:
                potassiumEntry = {}
                if 'resource' in entry:
                    if entry['resource']['resourceType'] == 'Observation':
                        resource = entry.get('resource', {})
                        potassiumEntry['value'] = resource.get('valueQuantity', {}).get('value', "")
                        if bool(potassiumEntry['value']):
                            potassiumEntry['effectiveDateTime'] = resource.get('effectiveDateTime', "")
                            callResponse.append(potassiumEntry)
            callResponse.sort(key=lambda x: x["effectiveDateTime"], reverse=True)
            if len(callResponse) > 0:
                results = callResponse[0]
            else:
                results['value'] = None
                results['effectiveDateTime'] = None
        except Exception as e:
            print("Error parsing Potassium:")
            print(e)
        return results

    def parseCreatinine(self, response):
        results = {}
        try:
            callResponse = []
            entries = response.get('entry', [])
            for entry in entries:
                creatinineEntry = {}
                if 'resource' in entry:
                    if entry['resource']['resourceType'] == 'Observation':
                        resource = entry.get('resource', {})
                        creatinineEntry['value'] = resource.get('valueQuantity', {}).get('value', "")
                        if bool(creatinineEntry['value']):
                            creatinineEntry['effectiveDateTime'] = resource.get('effectiveDateTime', "")
                            callResponse.append(creatinineEntry)
            callResponse.sort(key=lambda x: x["effectiveDateTime"], reverse=True)
            if len(callResponse) > 0:
                results = callResponse[0]
            else:
                results['value'] = None
                results['effectiveDateTime'] = None
        except Exception as e:
            print("Error parsing Creatinine:")
            print(e)
        return results
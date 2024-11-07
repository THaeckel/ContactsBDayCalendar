from webdav3.client import Client
from io import BytesIO, StringIO
import vobject
from datetime import datetime, timedelta
import argparse, os, uuid

def parseDate(date_str):
    for date_fmt in ('%Y-%m-%d', '%Y%m%d', '--%m%d'):
        try:
            return datetime.strptime(date_str, date_fmt)
        except:
            pass
    raise ValueError(f"could not parse date {date_str}")

def cleanUUID(uuid_str):
    return uuid_str.split("contacts-")[-1].split("uuid-")[-1]

def cleanName(name):
    clean = name.replace("  ", " ").replace("' '", " ")
    if clean.endswith(" "):
        clean = clean[:-1]
    return clean

def fixParents(name, owner):
    if name in {"Mama", "Papa", "mama", "papa"}:
        name += " von " + owner
    return name

class Contact:
    def __init__(self, carddav, owner):
        self.owner = owner[0].upper() + owner[1:]
        self.name = fixParents(cleanName(carddav.fn.value), self.owner)
        self.bday = parseDate(carddav.bday.value)
        self.uuid = uuid.UUID(cleanUUID(carddav.uid.value))

    def __str__(self):
        return f"{self.name}, {self.bday}, {self.uuid}" 
    
    def getUuidForYear(self, year):
        return uuid.UUID(int=self.uuid.int + year)
    
    def getBirthdayForYear(self, year):
        return datetime(day=self.bday.day, month=self.bday.month, year=year)
    
    def getAgeForYear(self, bday_year):
        age = None
        if self.bday.year > 1900:
            age = round((bday_year - self.bday).days / 365.25)
        return age
    
    def getSummary(self, bday_year):
        age = self.getAgeForYear(bday_year)
        summary = f"{self.name} hat Geburtstag"
        if age:
            summary += f" ({age})"
        return summary
    
    def getCalendarObject(self, year):
        bday_year = self.getBirthdayForYear(year)
        calendar = vobject.iCalendar()
        event = calendar.add('vevent')
        event.add('summary').value = self.getSummary(bday_year)
        event.add('dtstart').value = bday_year
        event.add('dtend').value = bday_year + timedelta(days=1)
        event.add('uid').value = str(self.getUuidForYear(year))
        return calendar, event.uid.value

parser = argparse.ArgumentParser(description='test')
parser.add_argument('--contacts_url', default=os.environ.get('WEBDAV_CONTACTS_URL'))
parser.add_argument('--calendar_url', default=os.environ.get('WEBDAV_CALENDAR_URL'))
parser.add_argument('--user', default=os.environ.get('WEBDAV_USER'))
parser.add_argument('--password', default=os.environ.get('WEBDAV_PASSWORD'))
parser.add_argument('--contacts_url2', default=None)
parser.add_argument('--user2', default=None)
parser.add_argument('--password2', default=None)
args = parser.parse_args()

def build_client(url, user, password):
    options = {
        "webdav_hostname": url,
        "webdav_login": user, # args.user
        "webdav_password": password, # args.password
        "webdav_override_methods": {
            'check': 'GET'
        }
    }

    client = Client(options)
    client.verify = True

    return client

def getContacts(client):
    contacts = []
    for vcf_file in client.list('/'):
        if not vcf_file.endswith('.vcf'):
            continue

        buff = BytesIO()
        client.download_from(
            buff=buff,
            remote_path=vcf_file
        )
        contacts += vobject.readComponents(buff.getvalue().decode('utf-8'))
    return contacts

def createContactList(contacts, owner):
    contact_list = []
    for contact in contacts:
        if not hasattr(contact, 'bday'):
            continue
        object = Contact(contact, owner)
        contact_list.append(object)
    return contact_list
        
def addContactListToDict(contactsDict, contactList):
    for contact in contactList:
        if contact.name not in contactsDict:
            contactsDict[contact.name] = contact
        else:
            print(f"Found {contact.name} in both contacts1 and contacts2")
            # merge birthday data from contacts2 to contacts1
            # check if bday is different in both contacts
            if contact.bday != contactsDict[contact.name].bday:
                # check if year is missing in one of the contacts
                if contact.bday.year > 1900 and contactsDict[contact.name].bday.year <= 1900:
                    contactsDict[contact.name] = contact
    return contactsDict

contactsDict = dict()
contacts_client = build_client(args.contacts_url, args.user, args.password)
carddav1 = getContacts(contacts_client)
contacts1 = createContactList(carddav1, args.user)
contactsDict = addContactListToDict(contactsDict, contacts1)
# check if second carddav is available
if args.contacts_url2 and args.user2 and args.password2:
    contacts_client2 = build_client(args.contacts_url2, args.user2, args.password2)
    carddav2 = getContacts(contacts_client2)
    contacts2 = createContactList(carddav2, args.user2)
    contactsDict = addContactListToDict(contactsDict, contacts2)

calendar_client = build_client(args.calendar_url, args.user, args.password)
curYear = datetime.now().year
for contact in contactsDict.values():
    try:
        for i in range(10):
            calendar,uid = contact.getCalendarObject(curYear + i)            
            calendar_client.upload_to(buff=calendar.serialize().encode('utf-8'), remote_path=f"{uid}.ics")
    except ValueError as e:
        print(f"{e}: {contact.fn.value}")
        continue

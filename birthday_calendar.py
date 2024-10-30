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
    return uuid_str.split("contacts-")[-1]

parser = argparse.ArgumentParser(description='test')
parser.add_argument('--contacts_url', default=os.environ.get('WEBDAV_CONTACTS_URL'))
parser.add_argument('--calendar_url', default=os.environ.get('WEBDAV_CALENDAR_URL'))
parser.add_argument('--user', default=os.environ.get('WEBDAV_USER'))
parser.add_argument('--password', default=os.environ.get('WEBDAV_PASSWORD'))
args = parser.parse_args()

def build_client(url):
    options = {
        "webdav_hostname": url,
        "webdav_login": args.user,
        "webdav_password": args.password,
        "webdav_override_methods": {
            'check': 'GET'
        }
    }

    client = Client(options)
    client.verify = True

    return client

contacts_client = build_client(args.contacts_url)
calendar_client = build_client(args.calendar_url)

for vcf_file in contacts_client.list('/'):
    if not vcf_file.endswith('.vcf'):
        continue

    buff = BytesIO()
    contacts_client.download_from(
        buff=buff,
        remote_path=vcf_file
    )

    contacts = vobject.readComponents(buff.getvalue().decode('utf-8'))
    for contact in contacts:
        print(contact.fn.value)

        if not hasattr(contact, 'bday'):
            continue

        try:
            bday = parseDate(contact.bday.value)

            for i in range(10):
                bday_year = datetime(day=bday.day, month=bday.month, year=datetime.now().year + i)

                age = None
                if bday.year > 1900:
                    age = round((bday_year - bday).days / 365.25)

                summary = f"{contact.fn.value} hat Geburstag"
                if age:
                    summary += f" ({age})"

                uid = uuid.UUID(int=uuid.UUID(cleanUUID(contact.uid.value)).int + bday_year.year)

                calendar = vobject.iCalendar()
                event = calendar.add('vevent')
                event.add('summary').value = summary
                event.add('dtstart').value = bday_year
                event.add('dtend').value = bday_year + timedelta(days=1)
                event.add('uid').value = str(uid)

                calendar_client.upload_to(buff=calendar.serialize().encode('utf-8'), remote_path=f"{uid}.ics")
        except ValueError as e:
            print(f"{e}: {contact.fn.value}")
            continue

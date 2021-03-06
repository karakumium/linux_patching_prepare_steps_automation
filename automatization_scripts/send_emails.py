#!/usr/bin/python3
import sqlite3
import datetime
import calendar
import random

cursor_patching_db = sqlite3.connect('./patching.db').cursor()
# cal=calendar.Calendar(firstweekday=6)
#
#
#
# cal=cal.monthdayscalendar(2018,1)
# print(cal)
#
# today=datetime.datetime.now()
#
# for i in range(0,5):
#     if today.day in cal[i]:
#         current_weekmonth=i
#
# today_window_code=cursor_patching_db.execute('SELECT CODE FROM WINDOW_CODE WHERE IDX=:weekmonth AND WEEKDAY=:weekday', {'weekmonth' : current_weekmonth, 'weekday': today.weekday()+1}).fetchone()
# today_patching_servers=cursor_patching_db.execute('SELECT SERVER_NAME FROM SERVERS WHERE WINDOW_CODE=:today_window_code', {'today_window_code' : today_window_code[0]}).fetchall()
# print(today_window_code)
# print(today_patching_servers)

import csv
import itertools


def extract_needed_servers(csv_file_name):
    csv_file_name = '1.csv'
    csv_file = open(csv_file_name)
    servers_for_sending_email = {}
    min_start_time = datetime.datetime.now() + datetime.timedelta(minutes=13)
    # max_start_time = datetime.datetime.now() + datetime.timedelta(minutes=30)
    max_start_time = datetime.datetime.now() + datetime.timedelta(hours=30)
    patching_schedule_csv = csv.reader(csv_file, delimiter=';')
    for row in itertools.islice(patching_schedule_csv, 1, None):
        patching_start_time = datetime.datetime.strptime(row[1], '%d.%m.%Y %H:%M')
        if patching_start_time > min_start_time and patching_start_time < max_start_time:
            servers_for_sending_email[row[5]] = row[1]
    # {'cent_os2': '04.01.2018 20:00'}
    return servers_for_sending_email


def extract_emails_and_so(servers):
    servers_contact = []
    for current_server in servers.keys():
        data_from_sqlite = cursor_patching_db.execute(
            'SELECT SERVER_NAME,SERVICE_OWNERS,CONTACT_EMAILS FROM SERVER_OWNERS WHERE SERVER_NAME=:current_server',
            {'current_server': current_server}).fetchone()
        if data_from_sqlite:
            servers_contact.append(data_from_sqlite + tuple([servers[current_server]]))
    return servers_contact


def prepare_email(server_for_sending_emails):
    server_so_email = [('cent_os4', 'Vodka Pivovich', 'vodka@vodka.com', 'Nagios main nodes', '04.01.2018 20:00'),
                       ('cent_os5', 'Vodka Pivovich', 'not_vodka@vodka.com', 'Nagios main nodes', '04.01.2018 20:00'),
                       ('cent_os6', 'Vodka Pivovich', 'vodka@vodka.com', 'Nagios main nodes', '04.01.2018 20:00'), \
                       ('cent_os7', 'Vodka Pivovich,Vodka2 Pivivich2,Vodka3 Pivovich3', 'vodka@vodka.com',
                        'Nagios main nodes', '04.01.2018 20:00'), (
                       'cent_os8', 'Vodka Pivovich,Vodka2 Pivivich2', 'vodka@vodka.com,vodka2@vodka.com', 'Nagios failover nodes',
                       '04.01.2018 20:00'), (
                       'cent_os9', 'Vodka Pivovich,Vodka2 Pivivich', 'vodka@vodka.com,vodka2@vodka.com', 'Nagios failover nodes',
                       '04.01.2018 20:00')]
    uniq_so_and_emails_set = []
    for current_server in server_so_email:
        uniq_so_and_emails_set.append((current_server[1], current_server[2], current_server[3], current_server[4]))
    uniq_so_and_emails_set = set(uniq_so_and_emails_set)
    common_servers = []
    for current_server_in_uniq in uniq_so_and_emails_set:
        counter = 0
        for current_server in server_so_email:
            for i in range(1, 5):
                if current_server[i] == current_server_in_uniq[i - 1]:
                    counter += 1
            if counter == 4:
                common_servers.append(current_server[0])
                params = current_server[1:]
            counter = 0
        email_sending(common_servers, params)
        common_servers.clear()


def email_sending(servers_group, params):
    so_str = ''
    services_owners = params[0].split(',')
    if len(services_owners) == 1:
        so_str = services_owners[0].split(' ')[0]
    elif len(services_owners) > 1:
        for i in services_owners[:-1]:
            so_str += (i.split(' ')[0]) + ', '
        so_str += str(' and ' + services_owners[-1].split(' ')[0])
        so_str = so_str.replace(',  and', ' and')

    servers_str=''
    if len(servers_group)==1:
        servers_str='on the %s server at %s CET.'% (servers_group[0],params[3].split(' ')[1])
    elif len(servers_group)>1:
        servers_str='on the following servers at {date} CET:\n'.format(date=params[3].split(' ')[1])+'\n'.join(servers_group)

    greeting=('Hi', 'Hello', 'Dear')[random.randint(0,2)]
    bye=('Best regards!', 'King regards!', 'We will inform you when patching is done.', 'See you!', 'Good luck!', 'Thanks!')[random.randint(0,5)]


    message = '{greeting} {SO},\n\nWe are going to install patches {servers}\n\n{bye}'.format(
        greeting=greeting, SO=so_str, date=params[3], servers=servers_str, bye=bye)
    subject = 'RFC XXXX: monthly Linux-patching (' + params[2] + ')'
    e_mails= params[1].split(',')
    print(subject)

    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email import encoders
    import io
    msg = MIMEMultipart()
    msg['Subject']=subject
    msg['From'] = "me"
    msg['To'] = e_mails
    f = io.StringIO(message)
    part = MIMEText(f.getvalue())
    msg.attach(part)
    encoders.encode_base64(part)
    s = smtplib.SMTP("smtp.my_organization.net")
    s.sendmail(msg['From'], msg['To'], msg.as_string())
    s.quit()


server_so_email_date = extract_emails_and_so(extract_needed_servers('1.csv'))
prepare_email(server_so_email_date)

import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta
from hrms_app.models import LeaveApplication
import requests
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from hrms_app.models import Holiday

def send_email(subject, template_name, context, from_email, recipient_list):
    """
    Send an email with both plain text and HTML content.

    :param subject: Subject of the email.
    :param template_name: The base name of the email template (without extension).
    :param context: Context data to render the template.
    :param from_email: Sender email address.
    :param recipient_list: List of recipient email addresses.
    """
    html_message = render_to_string(f"{template_name}.html", context)
    plain_message = strip_tags(html_message)

    send_mail(
        subject,
        plain_message,
        from_email,
        recipient_list,
        # html_message=html_message,
    )


def call_soap_api(device_instance):
    url = device_instance.api_link
    headers = {"Content-Type": "text/xml"}
    params = {"op": "GetTransactionsLog"}

    body = f"""<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
        <soap:Body>
            <GetTransactionsLog xmlns="http://tempuri.org/">
                <FromDateTime>{device_instance.from_date}</FromDateTime>
                <ToDateTime>{device_instance.to_date}</ToDateTime>
                <SerialNumber>{device_instance.serial_number}</SerialNumber>
                <UserName>{device_instance.username}</UserName>
                <UserPassword>{device_instance.password}</UserPassword>
                <strDataList>string</strDataList>
            </GetTransactionsLog>
        </soap:Body>
    </soap:Envelope>
    """

    response = requests.post(url, params=params, data=body, headers=headers)

    if response.status_code == 200:
        root = ET.fromstring(response.content)

        # Extracting data from the response
        log_result = root.find(".//{http://tempuri.org/}GetTransactionsLogResult").text
        str_data_list = root.find(".//{http://tempuri.org/}strDataList").text

        # Dictionary to store grouped data
        grouped_data = defaultdict(lambda: defaultdict(list))

        # Splitting and processing each line of str_data_list
        for line in str_data_list.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 2:
                emp_code = parts[0]
                log_time_str = " ".join(
                    parts[1:]
                )  # Join the remaining parts as log_time_str
                try:
                    log_time = datetime.strptime(log_time_str, "%Y-%m-%d %H:%M:%S")
                    date_key = log_time.date()

                    grouped_data[emp_code][date_key].append(log_time)
                except ValueError as e:
                    print(f"Issue parsing line: {line}. Error: {e}")
            else:
                print(f"Issue parsing line: {line}. Insufficient data.")

        return grouped_data

    else:
        print(f"Error: {response.status_code} - {response.reason}")


def is_weekend(date):
    return date.weekday() >= 6  # 5 = Saturday, 6 = Sunday


def is_holiday(date):
    return Holiday.objects.filter(start_date=date).exists()


def get_non_working_days(start, end):
    non_working_days = 0
    for n in range((end - start).days + 1):
        day = start + timedelta(n)
        if is_weekend(day) or is_holiday(day):
            non_working_days += 1
    return non_working_days




from rest_framework.response import Response

def create_response(status: str, message: str, data: dict = None, status_code: int = 200) -> Response:
    response_data = {
        "status": status,
        "message": message,
        "data": data
    }
    return Response(response_data, status=status_code)



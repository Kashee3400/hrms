# tasks.py (inside one of your Django apps)
from .models import *
from dotenv import load_dotenv
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from celery import shared_task
import tensorflow as tf
from django.conf import settings
import matplotlib.pyplot as plt
# from tensorflow.keras.preprocessing.image import load_img, img_to_array
from keras.api.preprocessing.image import load_img, img_to_array
import numpy as np
import os


load_dotenv()


@shared_task
def send_leave_application_notifications(application_id, protocol, domain):
    leave_application = LeaveApplication.objects.get(id=application_id)
    user = leave_application.appliedBy
    manager = user.reports_to

    def create_email_context(title, content, leave_application, protocol, domain):
        return {
            "title": title,
            "content": content,
            "detail_url": f"{protocol}://{domain}{reverse('leave_application_detail', kwargs={'slug': leave_application.slug})}",
        }

    def send_email(subject, content, recipient):
        context = create_email_context(
            subject, content, leave_application, protocol, domain
        )
        message = render_to_string("email/leave_application_email.txt", context)
        send_leave_application_email.delay(subject, message, [recipient])

    # Employee email content
    employee_content = (
        f"Dear {user.first_name},\n\n"
        f"Your leave application ({leave_application.applicationNo}) has been {leave_application.status}.\n\n"
        f"Leave Details:\n"
        f"- Start Date: {leave_application.startDate.date()}\n"
        f"- End Date: {leave_application.endDate.date()}\n"
        f"- Leave Type: {leave_application.leave_type.leave_type}\n"
        f"Thank you,\n"
        f"Your HR Team"
    )
    employee_email = user.official_email if user.official_email else user.email
    send_email("Leave Application Status", employee_content, employee_email)

    # Manager email content
    manager_content = (
        f"Dear {manager.first_name} {manager.last_name},\n\n"
        f"A leave application ({leave_application.applicationNo}) by {user.get_full_name()} has been {leave_application.status}.\n\n"
        f"Leave Details:\n"
        f"- Start Date: {leave_application.startDate.date()}\n"
        f"- End Date: {leave_application.endDate.date()}\n"
        f"- Leave Type: {leave_application.leave_type.leave_type}\n"
        f"You can review the application at the following link:"
    )
    send_email(
        "Leave Application Status",
        manager_content,
        manager.official_email if manager.official_email else manager.email,
    )


@shared_task
def send_leave_application_email(subject, message, recipient_list):
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)


@shared_task
def send_tour_notifications(tour_id, protocol, domain):
    user_tour = UserTour.objects.get(id=tour_id)
    user = user_tour.applied_by
    manager = user.reports_to

    def create_email_context(title, content, user_tour, protocol, domain):
        return {
            "title": title,
            "content": content,
            "detail_url": f"{protocol}://{domain}{reverse('tour_application_detail', kwargs={'slug': user_tour.slug})}",
        }

    def send_email(subject, content, recipient):
        context = create_email_context(subject, content, user_tour, protocol, domain)
        message = render_to_string("email/leave_application_email.txt", context)
        send_tour_application_email.delay(subject, message, [recipient])

    # Employee email content
    employee_content = (
        f"Dear {user.first_name},\n\n"
        f"Your tour application from ({user_tour.from_destination}) to ({user_tour.to_destination})  has been {user_tour.status}.\n\n"
        f"Tour Details:\n"
        f"- Boarding : {user_tour.from_destination} ({user_tour.start_date} {user_tour.start_time})\n"
        f"- Destination:  {user_tour.to_destination} ({user_tour.end_date} {user_tour.end_time})\n"
        f"- Status: {user_tour.status}\n"
        f"Thank you,\n"
        f"Your HR Team\n\n"
        f"You can review the tour detail at the following link:"
    )
    employee_email = user.official_email if user.official_email else user.email
    send_email("Tour Application Status", employee_content, employee_email)

    # Manager email content
    manager_content = (
        f"Dear {manager.first_name} {manager.last_name},\n\n"
        f"A Tour application requested by {user.get_full_name()} from ({user_tour.from_destination}) to ({user_tour.to_destination})  has been {user_tour.status}.\n\n"
        f"Tour Details:\n"
        f"- Boarding : {user_tour.from_destination} ({user_tour.start_date} {user_tour.start_time})\n"
        f"- Destination:  {user_tour.to_destination} ({user_tour.end_date} {user_tour.end_time})\n"
        f"- Status: {user_tour.status}\n"
        f"You can review the tour detail at the following link:"
    )
    send_email(
        "Tour Application Status",
        manager_content,
        manager.official_email if manager.official_email else manager.email,
    )


@shared_task
def send_tour_application_email(subject, message, recipient_list):
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)


@shared_task
def send_regularization_notification(regularization_id, protocol, domain):
    log = AttendanceLog.objects.get(id=regularization_id)
    user = log.applied_by
    manager = user.reports_to

    def create_email_context(title, content, log, protocol, domain):
        return {
            "title": title,
            "content": content,
            "detail_url": f"{protocol}://{domain}{reverse('event_detail', kwargs={'slug': log.slug})}",
        }

    def send_email(subject, content, recipient):
        context = create_email_context(subject, content, log, protocol, domain)
        message = render_to_string("email/leave_application_email.txt", context)
        send_regularization_email.delay(subject, message, [recipient])

    # Employee email content
    employee_content = (
        f"Dear {user.first_name},\n\n"
        f"Your regularization update. \n\n"
        f"Tour Details:\n"
        f"- {log.from_date} to {log.to_date}  ({log.reg_status}).\n"
        f"- Status: {log.status}\n"
        f"Thank you,\n"
        f"Your HR Team\n\n"
        f"You can review the tour detail at the following link:"
    )
    employee_email = user.official_email if user.official_email else user.email
    send_email("Regularization Status", employee_content, employee_email)

    # Manager email content
    manager_content = (
        f"Dear {manager.first_name} {manager.last_name},\n\n"
        f"A regularization requested by {user.get_full_name()} \n\n"
        f"Tour Details:\n"
        f"- from ({log.from_date}) to ({log.to_date})  has been {log.status}.\n"
        f"- Status: {log.status}\n"
        f"You can review the tour detail at the following link:"
    )
    send_email(
        "Tour Application Status",
        manager_content,
        manager.official_email if manager.official_email else manager.email,
    )


@shared_task
def send_regularization_email(subject, message, recipient_list):
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)


@shared_task
def train_model_task():
    data_dir = settings.UPLOAD_FOLDER
    train_datagen = tf.keras.preprocessing.image.ImageDataGenerator(rescale=1.0 / 255)
    val_datagen = tf.keras.preprocessing.image.ImageDataGenerator(rescale=1.0 / 255)

    train_data = train_datagen.flow_from_directory(
        directory=os.path.join(data_dir, "train"),
        target_size=(160, 160),
        batch_size=32,
        class_mode="categorical",
        shuffle=True,
    )

    val_data = val_datagen.flow_from_directory(
        directory=os.path.join(data_dir, "validation"),
        target_size=(160, 160),
        batch_size=32,
        class_mode="categorical",
        shuffle=True,
    )

    num_classes = len(train_data.class_indices)

    if os.path.exists(settings.MODEL_FILE.replace(".h5", ".keras")):
        model = tf.keras.models.load_model(settings.MODEL_FILE.replace(".h5", ".keras"))
        # Remove the last layer if necessary
        model.layers.pop()
        # Add a new Dense layer
        model.add(tf.keras.layers.Dense(num_classes, activation="softmax"))
    else:
        model = create_model(num_classes)

    model.add(tf.keras.layers.GlobalAveragePooling2D())
    model.add(tf.keras.layers.Dense(num_classes, activation="softmax"))

    model.compile(
        optimizer="adam",
        loss=tf.keras.losses.CategoricalCrossentropy(from_logits=True),
        metrics=["accuracy"],
    )
    model.summary()
    epochs = 10
    history = model.fit(train_data, validation_data=val_data, epochs=epochs)
    acc = history.history["accuracy"]
    model.save(settings.MODEL_FILE.replace(".h5", ".keras"))
    
    save_class_mapping(train_data.class_indices)

    val_acc = history.history["val_accuracy"]

    loss = history.history["loss"]
    val_loss = history.history["val_loss"]

    epochs_range = range(epochs)

    plt.figure(figsize=(8, 8))
    plt.subplot(1, 2, 1)
    plt.plot(epochs_range, acc, label="Training Accuracy")
    plt.plot(epochs_range, val_acc, label="Validation Accuracy")
    plt.legend(loc="lower right")
    plt.title("Training and Validation Accuracy")

    plt.subplot(1, 2, 2)
    plt.plot(epochs_range, loss, label="Training Loss")
    plt.plot(epochs_range, val_loss, label="Validation Loss")
    plt.legend(loc="upper right")
    plt.title("Training and Validation Loss")
    plt.show()


def save_class_mapping(class_indices):
    for employee_code, index in class_indices.items():
        EmployeeClassMapping.objects.update_or_create(
            employee_code=employee_code, defaults={"class_index": index}
        )


batch_size = 32
img_height = 180
img_width = 180


def create_model(num_classes):
    model = tf.keras.Sequential(
        [
            tf.keras.layers.Rescaling(
                1.0 / 255, input_shape=(img_height, img_width, 3)
            ),
            tf.keras.layers.Conv2D(16, 3, padding="same", activation="relu"),
            tf.keras.layers.MaxPooling2D(),
            tf.keras.layers.Conv2D(32, 3, padding="same", activation="relu"),
            tf.keras.layers.MaxPooling2D(),
            tf.keras.layers.Conv2D(64, 3, padding="same", activation="relu"),
            tf.keras.layers.MaxPooling2D(),
            tf.keras.layers.Flatten(),
            tf.keras.layers.Dense(128, activation="relu"),
            tf.keras.layers.Dense(num_classes),
        ]
    )
    model.compile(
        optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"]
    )
    return model

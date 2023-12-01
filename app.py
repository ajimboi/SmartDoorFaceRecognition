from flask import Flask, render_template, Response, request, redirect, url_for
import cv2
import face_recognition
import os
import base64
from datetime import datetime
import mysql.connector
import serial
import atexit
import time
import threading

app = Flask(__name__)
UPLOAD_FOLDER = 'C:\\xampp\\htdocs\\Kerja Ilman\\static\\images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

arduino_port = 'COM3'  
baud_rate = 9600
arduino = serial.Serial(arduino_port, baud_rate)
last_scan_time = time.time()

def connect_to_database():
    try:
        conn = mysql.connector.connect(user='jimboifyp', password='', host='localhost', port=2020, database='fypilman')
        print("Connection established successfully")
        return conn
    except mysql.connector.Error as error:
        print("Failed to connect to database: {}".format(error))

@app.route('/addpeople', methods=['GET', 'POST'])
def addpeople():
    if request.method == 'POST':
        name = request.form['name']
        gender = request.form['gender']
        file = request.files['image']

        conn = connect_to_database()
        if conn:
            cursor = conn.cursor()
            query = "INSERT INTO user (name, gender) VALUES (%s, %s)"
            values = (name, gender)
            cursor.execute(query, values)
            conn.commit()
            cursor.close()
            conn.close()

        # Create a folder based on the submitted name
        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], name)
        os.makedirs(user_folder, exist_ok=True)

        if file:
            # Save the image to the user's folder
            file.save(os.path.join(user_folder, file.filename))

        return redirect(url_for('success'))

    return render_template('AddPeople.html')


@app.route('/success')
def success():
    return render_template('Sucess.html')

# Function to load images from a directory
def load_images_from_folder(root_folder):
    image_list = []
    for person_folder in os.listdir(root_folder):
        person_path = os.path.join(root_folder, person_folder)
        if not os.path.isdir(person_path):
            continue
        person_name = person_folder  # Use the folder name as the person's name
        for filename in os.listdir(person_path):
            if filename.endswith(('.jpg', '.jpeg', '.png')):
                image_path = os.path.join(person_path, filename)
                image = face_recognition.load_image_file(image_path)
                image_list.append((person_name, image))
    return image_list

# Load reference images from the 'images' folder
reference_root_folder = 'C:\\xampp\\htdocs\\Kerja Ilman\\static\\images'
reference_images = load_images_from_folder(reference_root_folder)

# Initialize variables
known_face_encodings = []
known_face_names = []

# Extract face encodings and names from reference images
for person_name, image in reference_images:
    face_encoding = face_recognition.face_encodings(image)[0]
    known_face_encodings.append(face_encoding)
    known_face_names.append(person_name)

# Initialize the camera feed
video_capture = cv2.VideoCapture(0)

# Function to capture and save an unknown face
def capture_unknown_face(unknown_face):
    # Generate a unique filename based on the current timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    capture_filename = f'capture_{timestamp}.jpg'

    # Save the captured image to the "capture" folder
    capture_folder = 'C:\\xampp\\htdocs\\Kerja Ilman\\static\\capture'
    os.makedirs(capture_folder, exist_ok=True)
    capture_image_path = os.path.join(capture_folder, capture_filename)
    cv2.imwrite(capture_image_path, unknown_face)
    print(f"Unknown face saved: {capture_image_path}")

    # Insert image info into "capture" table
    insert_capture_info(capture_image_path)

def save_known_face(known_face, name):
    # Generate a unique filename based on the current timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    report_filename = f'report_{name}_{timestamp}.jpg'

    # Save the known face to the "report" folder
    report_folder = 'C:\\xampp\\htdocs\\Kerja Ilman\\static\\report'
    os.makedirs(report_folder, exist_ok=True)
    report_image_path = os.path.join(report_folder, report_filename)
    cv2.imwrite(report_image_path, known_face)
    print(f"Known face saved: {report_image_path}")

    # Insert image info into "report" table
    insert_report_info(report_image_path, name)

def insert_capture_info(image_path):
    conn = connect_to_database()
    if conn:
        try:
            cursor = conn.cursor()
            # Extract the filename from the full image path
            image_filename = os.path.basename(image_path)
            query = "INSERT INTO capture (image) VALUES (%s)"
            values = (image_filename,)
            cursor.execute(query, values)
            conn.commit()
            cursor.close()
        except Exception as e:
            print(f"Error inserting into 'capture' table: {e}")
        finally:
            conn.close()

def insert_report_info(image_path, name):
    conn = connect_to_database()
    if conn:
        try:
            cursor = conn.cursor()
            # Extract the filename from the full image path
            image_filename = os.path.basename(image_path)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            query = "INSERT INTO report (image, time, name) VALUES (%s, %s, %s)"
            values = (image_filename, timestamp, name)
            cursor.execute(query, values)
            conn.commit()
            cursor.close()
        except Exception as e:
            print(f"Error inserting into 'report' table: {e}")
        finally:
            conn.close()

@app.route('/grant_access', methods=['GET', 'POST'])
def grant_access():
    if request.method == 'POST':
        arduino.write(b'1')  # Send '1' to the Arduino
        time.sleep(15)  # Wait for 15 seconds
        arduino.write(b'0')  # Send '0' to the Arduino to deactivate the relay
        return render_template('LiveCamera.html')
    else:
        return render_template('LiveCamera.html')

# Function to process the camera feed for face recognition
def recognize_faces():
    global last_scan_time

    while True:
        # Capture a single frame from the webcam
        ret, frame = video_capture.read()

        # Find all face locations and encodings in the current frame
        face_locations = face_recognition.face_locations(frame)
        face_encodings = face_recognition.face_encodings(frame, face_locations)

        # Flag to indicate whether a known face is detected
        known_face_detected = False

        # Calculate the time difference in seconds
        current_time = time.time()
        time_diff = current_time - last_scan_time

        # Check if 15 seconds have passed since the last scan
        if time_diff >= 15:
            last_scan_time = current_time

            # Loop through each detected face
            for face_encoding, face_location in zip(face_encodings, face_locations):
                # Initialize name as "Unknown" for each face
                name = "Unknown"

                # Check if the face matches any of the reference images
                matches = face_recognition.compare_faces(known_face_encodings, face_encoding)

                if True in matches:
                    matched_names = [known_face_names[i] for i, match in enumerate(matches) if match]
                    name = ", ".join(matched_names)
                    # Save known faces to the "report" folder and database table "report"
                    (top, right, bottom, left) = face_location
                    known_face = frame[top:bottom, left:right]
                    save_known_face(known_face, name)
                    known_face_detected = True
                else:
                    # If face is unknown, capture and save the image
                    (top, right, bottom, left) = face_location
                    unknown_face = frame[top:bottom, left:right]
                    capture_image_path = capture_unknown_face(unknown_face)
                    insert_capture_info(capture_image_path)

                # Draw a rectangle and label on the face in the frame
                for (top, right, bottom, left) in face_locations:
                    cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
                    font = cv2.FONT_HERSHEY_DUPLEX
                    cv2.putText(frame, name, (left + 6, bottom - 6), font, 0.5, (255, 255, 255), 1)

            # Send a message to Arduino to control the relay
            if known_face_detected:
                arduino.write(b'1')  # Send '1' to Arduino to activate the relay
            else:
                arduino.write(b'0')  # Send '0' to Arduino to deactivate the relay

        # Convert the frame to JPEG format
        ret, jpeg = cv2.imencode('.jpg', frame)
        frame = jpeg.tobytes()

        # Yield the frame for displaying in the HTML template
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

        time.sleep(0.1)  # Adjust the sleep time as needed

# Close the serial connection when the program exits
atexit.register(arduino.close)

@app.route('/livecamera')
def livecamera():
    return render_template('LiveCamera.html')


@app.route('/video_feed')
def video_feed():
    # Return the processed camera feed as a response with content type 'multipart/x-mixed-replace'
    return Response(recognize_faces(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/listpeople')
def listpeople():
    conn = connect_to_database()
    
    if conn:
        try:
            cursor = conn.cursor()
            # Execute a SELECT query to retrieve data from your table
            cursor.execute("SELECT user_id, name, gender FROM user")
            
            # Fetch all rows from the result set
            rows = cursor.fetchall()
            
            # Close the cursor and database connection
            cursor.close()
            conn.close()
            
            # Render the template with the retrieved data
            return render_template('ListPeople.html', lists=rows)
        except Exception as e:
            print("Error fetching data from database:", str(e))
    
    # Handle any errors or return an empty gallery
    return render_template('ListPeople.html', lists=[])


@app.route('/report')
def report():
    conn = connect_to_database()
    
    if conn:
        try:
            cursor = conn.cursor()
            # Execute a SELECT query to retrieve data from your table
            cursor.execute("SELECT image, time, name FROM report")
            
            # Fetch all rows from the result set
            rows = cursor.fetchall()
            
            # Close the cursor and database connection
            cursor.close()
            conn.close()
            
            # Render the template with the retrieved data
            return render_template('Report.html', reports=rows)
        except Exception as e:
            print("Error fetching data from database:", str(e))
    
    # Handle any errors or return an empty gallery
    return render_template('Report.html', reports=[])

@app.route('/CaptureGallery')
def capture_gallery():
    # Connect to the database
    conn = connect_to_database()
    
    if conn:
        try:
            cursor = conn.cursor()
            # Execute a SELECT query to retrieve data from your table
            cursor.execute("SELECT image, time FROM capture")
            
            # Fetch all rows from the result set
            rows = cursor.fetchall()
            
            # Close the cursor and database connection
            cursor.close()
            conn.close()
            
            # Render the template with the retrieved data
            return render_template('CaptureGallery.html', captures=rows)
        except Exception as e:
            print("Error fetching data from database:", str(e))
    
    # Handle any errors or return an empty gallery
    return render_template('CaptureGallery.html', captures=[])



if __name__ == "__main__":
    scanning_thread = threading.Thread(target=recognize_faces)
    scanning_thread.start()
    app.run(host='0.0.0.0', port=5000, threaded=True)
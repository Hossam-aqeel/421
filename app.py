# app.py

from flask import Flask, render_template, request, redirect, url_for, jsonify
from model import DrugPredictor
import random
import threading

app = Flask(__name__)
app.secret_key = "M0hs3n#H0S$@m"  # Replace with your chosen secret key

# Initialize the DrugPredictor
predictor = DrugPredictor(data_path='DatasetML.csv')  # Adjust the path if needed

# Lock for thread-safe access to measurement_data
data_lock = threading.Lock()

# Global data store for measurement data
measurement_data = {
    'measurement_order': [],
    'sensor_data': {}
}

# Route to select measurement order
@app.route('/')
def home():
    with data_lock:
        # Clear global measurement data for a new patient
        measurement_data['measurement_order'] = []
        measurement_data['sensor_data'] = {}
    return render_template(
        'select_measurement.html',
        title="Health Profile"
    )

# Route to handle measurement selection
@app.route('/select_measurement', methods=['POST'])
def select_measurement():
    # User chooses which measurement to perform first
    first_measurement = request.form.get('first_measurement').lower()
    if first_measurement in ['temperature', 'pulse']:
        with data_lock:
            # Store the measurement order in the global data
            second_measurement = 'temperature' if first_measurement == 'pulse' else 'pulse'
            measurement_data['measurement_order'] = [first_measurement, second_measurement]
            measurement_data['sensor_data'] = {}  # Reset sensor data
            print(f"[select_measurement] Measurement order set: {measurement_data['measurement_order']}")
        return redirect(url_for('measure'))
    else:
        # Invalid selection, redirect back to home
        return redirect(url_for('home'))

# Route to handle measurement process
@app.route('/measure')
def measure():
    with data_lock:
        measurement_order = measurement_data.get('measurement_order', [])
        sensor_data = measurement_data.get('sensor_data', {})
    if not measurement_order:
        # No measurement order selected, redirect to home
        return redirect(url_for('home'))

    # Determine the next measurement to perform
    current_measurement = None
    for measurement in measurement_order:
        if measurement not in sensor_data:
            current_measurement = measurement
            break
    else:
        # All measurements completed, proceed to display results
        return redirect(url_for('display_measurements'))

    print(f"[measure] Current Measurement: {current_measurement}")
    print(f"[measure] Sensor Data: {sensor_data}")

    # Render the measurement template to simulate measurement
    return render_template(
        'measure.html',
        measurement=current_measurement,
        title=f"Measure {current_measurement.capitalize()}"
    )

# Endpoint to indicate if pulse data is needed
@app.route('/need_pulse_data')
def need_pulse_data():
    with data_lock:
        measurement_order = measurement_data.get('measurement_order', [])
        sensor_data = measurement_data.get('sensor_data', {})
    current_measurement = None

    # Determine which measurement we're waiting for
    for measurement in measurement_order:
        if measurement not in sensor_data:
            current_measurement = measurement
            break

    print(f"[need_pulse_data] Current Measurement: {current_measurement}")
    print(f"[need_pulse_data] Measurement Order: {measurement_order}")
    print(f"[need_pulse_data] Sensor Data: {sensor_data}")

    if current_measurement == 'pulse':
        return jsonify({'need_pulse': True})
    else:
        return jsonify({'need_pulse': False})

# Endpoint to receive sensor data from ESP32
@app.route('/upload_sensor_data', methods=['POST'])
def upload_sensor_data():
    measurement = request.form.get('measurement', '').lower()
    value = request.form.get('value')

    with data_lock:
        measurement_order = measurement_data.get('measurement_order', [])
        sensor_data = measurement_data.get('sensor_data', {})
    current_measurement = None

    for m in measurement_order:
        if m not in sensor_data:
            current_measurement = m
            break

    print(f"[upload_sensor_data] Current Measurement Expected: {current_measurement}")
    print(f"[upload_sensor_data] Received Measurement: {measurement}, Value: {value}")

    if current_measurement == measurement and value:
        try:
            value = float(value)
            with data_lock:
                sensor_data[measurement] = value
                measurement_data['sensor_data'] = sensor_data
            print(f"Received sensor data - {measurement.capitalize()}: {value}")
            return jsonify({'status': 'success'}), 200
        except ValueError:
            print(f"Invalid data format for {measurement}: {value}")
            return jsonify({'status': 'error', 'message': 'Invalid data format'}), 400
    else:
        # Not expecting this measurement now
        print(f"[upload_sensor_data] Measurement not expected now.")
        print(f"Expected: {current_measurement}, but got: {measurement}")
        return jsonify({'status': 'error', 'message': 'Measurement not expected now'}), 400

@app.route('/simulate_temperature')
def simulate_temperature():
    temperature = round(random.uniform(36.0, 38.0), 1)
    with data_lock:
        sensor_data = measurement_data.get('sensor_data', {})
        sensor_data['temperature'] = temperature
        measurement_data['sensor_data'] = sensor_data

    print(f"Simulated temperature: {temperature}")
    return jsonify({'status': 'success', 'temperature': temperature})

# Endpoint to provide sensor data to the web page
@app.route('/get_sensor_data')
def get_sensor_data():
    with data_lock:
        sensor_data = measurement_data.get('sensor_data', {})
        measurement_order = measurement_data.get('measurement_order', [])
    current_measurement = None

    # Determine which measurement we're waiting for
    for measurement in measurement_order:
        if measurement not in sensor_data:
            current_measurement = measurement
            break

    print(f"[get_sensor_data] Current Measurement: {current_measurement}")
    print(f"[get_sensor_data] Sensor Data: {sensor_data}")

    if current_measurement == 'pulse':
        # Waiting for pulse data
        return jsonify({'pulse': sensor_data.get('pulse', None)})
    elif current_measurement == 'temperature':
        # Waiting for temperature data
        return jsonify({'temperature': sensor_data.get('temperature', None)})
    else:
        # All measurements completed
        return jsonify({'done': True})

# Route to display measurements
@app.route('/display_measurements')
def display_measurements():
    with data_lock:
        sensor_data = measurement_data.get('sensor_data', {})
    if 'temperature' in sensor_data and 'pulse' in sensor_data:
        # Check if readings are normal
        temperature = sensor_data['temperature']
        bpm = sensor_data['pulse']

        print(f"[display_measurements] Temperature: {temperature}, BPM: {bpm}")

        if 36.0 <= temperature <= 38.0 and 60 <= bpm <= 100:
            # Readings are normal, proceed to the prediction form
            return render_template(
                'display_measurements.html',
                temperature=temperature,
                bpm=bpm,
                normal=True,
                title="Measurement Results"
            )
        else:
            # Readings are abnormal
            return render_template(
                'display_measurements.html',
                temperature=temperature,
                bpm=bpm,
                normal=False,
                title="Measurement Results"
            )
    else:
        # Missing measurements, redirect to measurement page
        print("[display_measurements] Missing measurements, redirecting to measure")
        return redirect(url_for('measure'))

# Route to handle the 'Proceed to Prediction' action
@app.route('/proceed_to_prediction')
def proceed_to_prediction():
    with data_lock:
        sensor_data = measurement_data.get('sensor_data', {})
    if 'temperature' in sensor_data and 'pulse' in sensor_data:
        return render_template(
            'form.html',
            features=predictor.feature_columns,
            error=None,
            title="Drug Prediction for Liver Disease Patients"
        )
    else:
        return redirect(url_for('home'))

# Route to handle predictions
@app.route('/predict', methods=['POST'])
def predict():
    patient_data = {}
    error_message = None

    for feature in predictor.feature_columns:
        value = request.form.get(feature)
        if value is None or value.strip() == '':
            error_message = f"Missing value for feature '{feature}'. Please fill out all fields."
            break
        # Handle categorical features
        if feature in ['Sex', 'Ascites', 'Hepatomegaly', 'Spiders', 'Edema', 'Status']:
            patient_data[feature] = value.strip()
        else:
            try:
                patient_data[feature] = float(value)
            except ValueError:
                error_message = f"Invalid value for feature '{feature}': '{value}'. Please enter valid numerical values."
                break

    if error_message:
        return render_template(
            'form.html',
            features=predictor.feature_columns,
            error=error_message,
            title="Drug Prediction for Liver Disease Patients"
        )

    predicted_drug = predictor.predict_drug(patient_data)

    # Reset measurement data for new patient after prediction
    with data_lock:
        measurement_data['measurement_order'] = []
        measurement_data['sensor_data'] = {}

    return render_template(
        'result.html',
        predicted_drug=predicted_drug,
        title="Prediction Result"
    )

if __name__ == '__main__':
    # Run the app with threading enabled
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
import pandas as pd
import numpy as np
import requests
import gzip
from io import BytesIO
from flasgger import Swagger
import zipfile

app = Flask(__name__)

# Swagger config
app.config['SWAGGER'] = {
    'title': 'Red Wine Quality Prediction API',
    'uiversion': 3
}
swagger = Swagger(app)

# SQLite DB setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///red_wines.db'
db = SQLAlchemy(app)

# Define a database model
class Wine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fixed_acidity = db.Column(db.Float, nullable=False)
    volatile_acidity = db.Column(db.Float, nullable=False)
    citric_acid = db.Column(db.Float, nullable=False)
    residual_sugar = db.Column(db.Float, nullable=False)
    chlorides = db.Column(db.Float, nullable=False)
    free_sulfur_dioxide = db.Column(db.Float, nullable=False)
    total_sulfur_dioxide = db.Column(db.Float, nullable=False)
    density = db.Column(db.Float, nullable=False)
    ph = db.Column(db.Float, nullable=False)
    sulphates = db.Column(db.Float, nullable=False)
    alcohol = db.Column(db.Float, nullable=False)
    quality = db.Column(db.Float, nullable=False)



# Create the database
with app.app_context():
    db.create_all()

def preprocess_data(df):

    df = df.dropna()
    return df

model = None


@app.route('/reload', methods=['POST'])
def reload_data():
    '''
    Reload data from the Red Wine dataset, clear the database, load new data, and return summary stats
    ---
    responses:
      200:
        description: Summary statistics of reloaded data
    '''
    global model

    # Step 1: Download and decompress data
    url = 'https://archive.ics.uci.edu/static/public/186/wine+quality.zip'
    response = requests.get(url)
    compressed_file = BytesIO(response.content)

    with zipfile.ZipFile(compressed_file) as z:
        with z.open('winequality-red.csv') as decompressed_file:
            wines = pd.read_csv(decompressed_file, delimiter=';')


    # Step 3: Clear the database
    db.session.query(Wine).delete()

    # Step 4: Process data and insert it into the database
    wines = wines.dropna()

    for _, row in wines.iterrows():
        new_wine = Wine(
            fixed_acidity=row['fixed acidity'],
            volatile_acidity=row['volatile acidity'],
            citric_acid=row['citric acid'],
            residual_sugar=row['residual sugar'],
            chlorides=row['chlorides'],
            free_sulfur_dioxide=row['free sulfur dioxide'],
            total_sulfur_dioxide=row['total sulfur dioxide'],
            density=row['density'],
            ph=row['pH'],
            sulphates=row['sulphates'],
            alcohol=row['alcohol'],
            quality=row['quality']
        )
        db.session.add(new_wine)
    db.session.commit()

    # Step 5: Preprocess and train model
    df = preprocess_data(wines)
    X = df.drop(columns='quality')
    y = df['quality']
    model = LinearRegression()
    model.fit(X, y)

    # Step 6: Generate summary statistics
    summary = {
        'total_wines': int(len(wines)),
        'average_quality': float(wines['quality'].mean()),
        'min_quality': float(wines['quality'].min()),
        'max_quality': float(wines['quality'].max()),
        'average_alcohol': float(wines['alcohol'].mean()),
        'average_pH': float(wines['pH'].mean())
    }

    return jsonify(summary)
@app.route('/predict', methods=['POST'])
def predict():
    '''
    Predict the quality of a wine based on its physicochemical properties
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            fixed_acidity:
              type: number
            volatile_acidity:
              type: number
            citric_acid:
              type: number
            residual_sugar:
              type: number
            chlorides:
              type: number
            free_sulfur_dioxide:
              type: number
            total_sulfur_dioxide:
              type: number
            density:
              type: number
            ph:
              type: number
            sulphates:
              type: number
            alcohol:
              type: number
    responses:
      200:
        description: Predicted wine quality
    '''
    global model

    if model is None:
        return jsonify({"error": "Model not trained. Please POST to /reload first."}), 400

    data = request.json
    try:
        features = [
            'fixed_acidity', 'volatile_acidity', 'citric_acid', 'residual_sugar',
            'chlorides', 'free_sulfur_dioxide', 'total_sulfur_dioxide', 'density',
            'ph', 'sulphates', 'alcohol'
        ]

        input_data = [pd.to_numeric(data.get(feat), errors='coerce') for feat in features]

        if any(pd.isna(input_data)):
            return jsonify({"error": "Missing or invalid numeric input fields"}), 400

        input_array = np.array(input_data).reshape(1, -1)
        predicted_quality = model.predict(input_array)[0]

        return jsonify({"predicted_quality": predicted_quality})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
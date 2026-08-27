from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import pandas as pd
import joblib

from difflib import SequenceMatcher


# ==========================================
# CREATE FASTAPI APP
# ==========================================

app = FastAPI(
    title="AI Finance Controller API",
    description="AI-powered financial transaction reconciliation system",
    version="1.0"
)


# ==========================================
# CORS
# Allows frontend to connect to backend
# ==========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# LOAD TRAINED ML MODEL
# ==========================================

model = joblib.load(
    "transaction_matching_model.pkl"
)

features = joblib.load(
    "model_features.pkl"
)


# ==========================================
# INPUT MODEL FOR SINGLE PREDICTION
# ==========================================

class TransactionPair(BaseModel):

    company_vendor: str
    bank_vendor: str

    company_amount: float
    bank_amount: float

    company_date: str
    bank_date: str

    company_reference: str
    bank_reference: str


# ==========================================
# HELPER FUNCTION:
# CALCULATE TEXT SIMILARITY
# ==========================================

def calculate_similarity(text1, text2):

    return SequenceMatcher(
        None,
        str(text1).lower(),
        str(text2).lower()
    ).ratio()


# ==========================================
# HELPER FUNCTION:
# CREATE FEATURES FOR ML MODEL
# ==========================================

def create_features(company, bank):

    # Vendor similarity

    vendor_similarity = calculate_similarity(
        company["vendor"],
        bank["vendor"]
    )


    # Amount difference

    amount_difference = abs(
        float(company["amount"]) -
        float(bank["amount"])
    )


    # Amount difference percentage

    if float(company["amount"]) != 0:

        amount_difference_percentage = (
            amount_difference /
            float(company["amount"])
        )

    else:

        amount_difference_percentage = 0


    # Date difference

    company_date = pd.to_datetime(
        company["date"]
    )

    bank_date = pd.to_datetime(
        bank["date"]
    )

    date_difference_days = abs(
        (company_date - bank_date).days
    )


    # Reference match

    reference_match = int(
        str(company["reference"]) ==
        str(bank["reference"])
    )


    return {
        "vendor_similarity":
            vendor_similarity,

        "amount_difference":
            amount_difference,

        "amount_difference_percentage":
            amount_difference_percentage,

        "date_difference_days":
            date_difference_days,

        "reference_match":
            reference_match
    }


# ==========================================
# HOME ROUTE
# ==========================================

@app.get("/")
def home():

    return {
        "message":
            "AI Finance Controller API is running successfully!"
    }


# ==========================================
# HEALTH CHECK
# ==========================================

@app.get("/health")
def health():

    return {
        "status": "healthy",
        "model_loaded": True
    }


# ==========================================
# SINGLE TRANSACTION PREDICTION
# ==========================================

@app.post("/predict")
def predict_transaction(
    data: TransactionPair
):

    try:

        # Vendor similarity

        vendor_similarity = calculate_similarity(
            data.company_vendor,
            data.bank_vendor
        )


        # Amount difference

        amount_difference = abs(
            data.company_amount -
            data.bank_amount
        )


        # Amount difference percentage

        if data.company_amount != 0:

            amount_difference_percentage = (
                amount_difference /
                data.company_amount
            )

        else:

            amount_difference_percentage = 0


        # Date difference

        company_date = pd.to_datetime(
            data.company_date
        )

        bank_date = pd.to_datetime(
            data.bank_date
        )

        date_difference_days = abs(
            (company_date - bank_date).days
        )


        # Reference match

        reference_match = int(
            data.company_reference ==
            data.bank_reference
        )


        # Create model input

        input_data = pd.DataFrame([{

            "vendor_similarity":
                vendor_similarity,

            "amount_difference":
                amount_difference,

            "amount_difference_percentage":
                amount_difference_percentage,

            "date_difference_days":
                date_difference_days,

            "reference_match":
                reference_match

        }])


        # Ensure correct feature order

        input_data = input_data[
            features
        ]


        # Make prediction

        prediction = model.predict(
            input_data
        )[0]


        # Get probability of MATCH class

        probabilities = model.predict_proba(
            input_data
        )[0]


        class_index = list(
            model.classes_
        ).index(1)


        probability = probabilities[
            class_index
        ]


        return {

            "prediction":
                "MATCH"
                if prediction == 1
                else "NOT MATCH",

            "match_confidence":
                round(
                    float(probability),
                    4
                ),

            "features_used": {

                "vendor_similarity":
                    round(
                        vendor_similarity,
                        4
                    ),

                "amount_difference":
                    amount_difference,

                "amount_difference_percentage":
                    round(
                        amount_difference_percentage,
                        4
                    ),

                "date_difference_days":
                    date_difference_days,

                "reference_match":
                    reference_match
            }

        }


    except Exception as e:

        return {

            "error":
                str(e),

            "error_type":
                type(e).__name__

        }


# ==========================================
# RECONCILE TWO CSV FILES
# ==========================================

@app.post("/reconcile")
async def reconcile_transactions(

    company_file: UploadFile = File(...),

    bank_file: UploadFile = File(...)

):

    try:

        # ----------------------------------
        # READ CSV FILES
        # ----------------------------------

        company_df = pd.read_csv(
            company_file.file
        )

        bank_df = pd.read_csv(
            bank_file.file
        )


        # ----------------------------------
        # CHECK REQUIRED COLUMNS
        # ----------------------------------

        required_columns = [

            "transaction_id",

            "date",

            "vendor",

            "amount",

            "reference"

        ]


        missing_company = [

            column

            for column in required_columns

            if column not in company_df.columns

        ]


        missing_bank = [

            column

            for column in required_columns

            if column not in bank_df.columns

        ]


        if missing_company:

            return {

                "error":
                    "Missing columns in company file",

                "missing_columns":
                    missing_company,

                "available_columns":
                    company_df.columns.tolist()

            }


        if missing_bank:

            return {

                "error":
                    "Missing columns in bank file",

                "missing_columns":
                    missing_bank,

                "available_columns":
                    bank_df.columns.tolist()

            }


        # ----------------------------------
        # STORE RESULTS
        # ----------------------------------

        results = []


        # Prevent same bank transaction
        # from being matched multiple times

        used_bank_transactions = set()


        # ----------------------------------
        # LOOP THROUGH COMPANY TRANSACTIONS
        # ----------------------------------

        for _, company in company_df.iterrows():


            best_match = None

            best_confidence = 0

            best_bank_index = None


            # ----------------------------------
            # COMPARE WITH BANK TRANSACTIONS
            # ----------------------------------

            for bank_index, bank in bank_df.iterrows():


                # Skip already matched
                # bank transactions

                if bank_index in used_bank_transactions:

                    continue


                # Create ML features

                feature_data = create_features(
                    company,
                    bank
                )


                # Convert to DataFrame

                input_data = pd.DataFrame([
                    feature_data
                ])


                # Ensure feature order
                # matches training data

                input_data = input_data[
                    features
                ]


                # Get prediction probability

                probabilities = model.predict_proba(
                    input_data
                )[0]


                # Get probability
                # for class 1 = MATCH

                class_index = list(
                    model.classes_
                ).index(1)


                probability = probabilities[
                    class_index
                ]


                # Save best match

                if probability > best_confidence:

                    best_confidence = probability

                    best_match = bank

                    best_bank_index = bank_index


            # ----------------------------------
            # DECIDE MATCH STATUS
            # ----------------------------------

            if best_match is None:

                status = "UNMATCHED"

                bank_transaction_id = None


            elif best_confidence >= 0.80:

                status = "MATCHED"


                used_bank_transactions.add(
                    best_bank_index
                )


                bank_transaction_id = str(
                    best_match[
                        "transaction_id"
                    ]
                )


            elif best_confidence >= 0.50:

                status = "POSSIBLE MATCH"


                bank_transaction_id = str(
                    best_match[
                        "transaction_id"
                    ]
                )


            else:

                status = "UNMATCHED"

                bank_transaction_id = None


            # ----------------------------------
            # SAVE RESULT
            # ----------------------------------

            results.append({

                "company_transaction_id":

                    str(
                        company[
                            "transaction_id"
                        ]
                    ),


                "bank_transaction_id":

                    bank_transaction_id,


                "status":

                    status,


                "confidence":

                    round(
                        float(
                            best_confidence
                        ),
                        4
                    )

            })


        # ======================================
        # CREATE SUMMARY
        # ======================================

        results_df = pd.DataFrame(
            results
        )


        matched_count = len(

            results_df[

                results_df[
                    "status"
                ] == "MATCHED"

            ]

        )


        possible_count = len(

            results_df[

                results_df[
                    "status"
                ] == "POSSIBLE MATCH"

            ]

        )


        unmatched_count = len(

            results_df[

                results_df[
                    "status"
                ] == "UNMATCHED"

            ]

        )


        # ======================================
        # RETURN RESULTS
        # ======================================

        return {

            "summary": {

                "total_company_transactions":

                    len(company_df),


                "matched":

                    matched_count,


                "possible_matches":

                    possible_count,


                "unmatched":

                    unmatched_count,


                "match_rate":

                    round(

                        (
                            matched_count /
                            len(company_df)
                        ) * 100,

                        2

                    )

                    if len(company_df) > 0

                    else 0

            },


            "results":

                results

        }


    # ==========================================
    # ERROR HANDLING
    # ==========================================

    except Exception as e:

        return {

            "error":

                str(e),

            "error_type":

                type(e).__name__

        }
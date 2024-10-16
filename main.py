"""
- BC ATM just stores the DID and serves VC upon successful DID issues
- Forward PII sent from dashboard to the BC
    - Use a very basic DB to store PII hashes that were used to generate the DID
- Forward VC requests to the BC
"""

import hashlib
import json
import logging
import os
from typing import Generator, List

from eth_account import Account
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, select
from starlette.responses import JSONResponse
from web3 import Web3

# Blockchain and Database setup
BLOCKCHAIN_URL = "http://127.0.0.1:8545"  # Hardhat blockchain
DASHBOARD_URL = "http://127.0.0.1:5173"  # Dashboard URL
DATABASE_URL = "sqlite:///./mainDatabase.db"

# File paths for contract data
DEPLOYED_ADDRESSES_PATH = (
    "../blockchain/ignition/deployments/chain-31337/deployed_addresses.json"
)
ABI_PATH = "../blockchain/ignition/deployments/chain-31337/artifacts/DIDRegistry#DIDRegistry.json"

# Web3 Setup
w3 = Web3(Web3.HTTPProvider(BLOCKCHAIN_URL))
if not w3.is_connected():
    raise Exception("Unable to connect to blockchain")

# Setup DB On Server Start
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# FastAPI setup
app = FastAPI()

# Set up logging
logging.basicConfig(level=logging.INFO)

# CORS setup to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request, call_next):
    logging.info(f"Request: {request.method} {request.url}")
    logging.info(f"Headers: {request.headers}")

    if request.method == "OPTIONS":
        logging.info("Received an OPTIONS request.")
        print(f"request.headers: {request.headers}")
        print(f"request.url: {request.url}")
        print(f"request.method: {request.method}")
        print(f"request.client: {request.client}")
        print(f"request.state: {request.state}")
        print(f"request.scope: {request.scope}")
        print(f"request.receive: {request.receive}")
        print(f"request.stream: {request.stream}")
        print(f"request.url_for: {request.url_for}")
        print(f"request.base_url: {request.base_url}")
        print(f"request.url: {request.url}")

        # return JSONResponse(
        #     content={"message": "CORS preflight response"}, status_code=200
        # )

    try:
        response = await call_next(request)
    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        print(f"request.headers: {request.headers}")
        print(f"request.url: {request.url}")
        print(f"request.method: {request.method}")
        print(f"request.client: {request.client}")
        print(f"request.state: {request.state}")
        print(f"request.scope: {request.scope}")
        print(f"request.receive: {request.receive}")
        print(f"request.stream: {request.stream}")
        print(f"request.url_for: {request.url_for}")
        print(f"request.base_url: {request.base_url}")
        print(f"request.url: {request.url}")
        raise

    return response


# Autogenerated private key for signing transactions
private_key = None
account = None

# Load deployed contract addresses and ABI on startup
CONTRACT_ADDRESS = None
ABI = None


# Connect to the DB
def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


# File paths
ACCOUNT_FILE_PATH = "account.json"  # Path to store the account data


@app.on_event("startup")
def on_startup():
    global CONTRACT_ADDRESS, ABI, private_key, account

    # Check if account file exists
    if os.path.exists(ACCOUNT_FILE_PATH):
        # Load the existing account from the JSON file
        with open(ACCOUNT_FILE_PATH, "r") as file:
            account_data = json.load(file)
            account = Account.from_key(
                account_data["private_key"]
            )  # Load account from private key
            private_key = account.key.hex()  # Get the private key
            logging.info(f"Loaded account: {account.address}")
    else:
        # Automatically generate a new Ethereum account
        account = Account.create()  # Create a new account
        private_key = account.key.hex()  # Get the private key

        # Save the new account to a JSON file
        with open(ACCOUNT_FILE_PATH, "w") as file:
            json.dump({"address": account.address, "private_key": private_key}, file)
        logging.info(f"Generated new account: {account.address}")

    # Read contract address
    with open(DEPLOYED_ADDRESSES_PATH, "r") as file:
        deployed_addresses = json.load(file)
        CONTRACT_ADDRESS = deployed_addresses["DIDRegistry#DIDRegistry"]

    # Read ABI
    with open(ABI_PATH, "r") as file:
        abi_data = json.load(file)
        ABI = abi_data["abi"]

    # Create tables in the database
    SQLModel.metadata.create_all(engine)

    logging.info(f'Server started successfully, DB created at "{DATABASE_URL}"')
    logging.info(f"Using account: {account.address}")
    logging.info(f"Contract Address: {CONTRACT_ADDRESS}")
    logging.info(f"ABI: {ABI}")


# @app.on_event("startup")
# def on_startup():
#     global CONTRACT_ADDRESS, ABI, private_key, account

#     # Use specified account and private key
#     account = Account.from_key(
#         "0xdf57089febbacf7ba0bc227dafbffa9fc08a93fdc68e1e42411a14efcf23656e"
#     )
#     private_key = account.key.hex()

#     # Read contract address
#     with open(DEPLOYED_ADDRESSES_PATH, "r") as file:
#         deployed_addresses = json.load(file)
#         CONTRACT_ADDRESS = deployed_addresses["DIDRegistry#DIDRegistry"]

#     # Read ABI
#     with open(ABI_PATH, "r") as file:
#         abi_data = json.load(file)
#         ABI = abi_data["abi"]

#     # Create tables in the database
#     SQLModel.metadata.create_all(engine)

#     logging.info(f'Server started successfully, DB created at "{DATABASE_URL}"')
#     logging.info(f"Using specified account: {account.address}")
#     logging.info(f"Contract Address: {CONTRACT_ADDRESS}")
#     logging.info(f"ABI: {ABI}")


# SQLModel table for user data
class User(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    email_hash: str
    fName: str  # First Name
    lName: str  # Last Name
    email: str  # Email
    phone: str  # Phone
    vc: str = Field(default=None, nullable=True)  # Allow vc to be nullable


# Models for API requests
class DIDRequest(BaseModel):
    fName: str
    lName: str
    email: str
    phone: str


class VCRequest(BaseModel):
    email: str
    vc_type: str
    claims: List[dict]


################################################################
###################### Blockchain Interaction ##################
################################################################


# Contract setup (fetch dynamically on each request)
def get_contract():
    if not CONTRACT_ADDRESS or not ABI:
        raise HTTPException(status_code=500, detail="Contract data not loaded")
    return w3.eth.contract(address=w3.to_checksum_address(CONTRACT_ADDRESS), abi=ABI)


# Utility function to hash PII data
def hash_pii(fName, lName, email, phone):
    data = f"{fName}{lName}{email}{phone}".encode("utf-8")
    return hashlib.sha256(data).hexdigest()


@app.post("/register_did")
def register_did(did_data: DIDRequest, db: Session = Depends(get_session)):
    try:
        if (
            not did_data.fName
            or not did_data.lName
            or not did_data.email
            or not did_data.phone
        ):
            raise HTTPException(status_code=400, detail="Missing PII data")

        print(f"[SUCCESS]: Received PII: {did_data.model_dump()}\n")

        # Hash the PII
        email_hash = hash_pii(
            did_data.fName, did_data.lName, did_data.email, did_data.phone
        )

        # Print Hash
        print(f"[SUCCESS]: Hashed PII: {email_hash}\n")

        # Check if DID already exists
        statement = select(User).where(User.email_hash == email_hash)
        existing_user = db.exec(statement).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="DID already registered")
        else:
            print(f"[SUCCESS]: Registering DID for {did_data.email}\n")

        # Register DID on blockchain
        contract = get_contract()
        txn = contract.functions.registerDID(
            f"did:example:{did_data.email}", [], []  # Public keys and services
        ).build_transaction(
            {
                "from": account.address,
                "nonce": w3.eth.get_transaction_count(account.address),
                "gas": 6721975,
                "gasPrice": w3.to_wei("1", "gwei"),
            }
        )

        # Print Transaction
        print(f"[SUCCESS]: Transaction: {txn}\n")

        # Sign and send transaction
        signed_txn = w3.eth.account.sign_transaction(txn, private_key=private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        w3.eth.wait_for_transaction_receipt(tx_hash)

        # Print Transaction Hash
        print(f"[SUCCESS]: Transaction Hash: {tx_hash.hex()}\n")

        # Store PII and email hash in the database
        new_user = User(
            email_hash=email_hash,
            fName=did_data.fName,
            lName=did_data.lName,
            email=did_data.email,
            phone=did_data.phone,
            vc="None",
        )
        db.add(new_user)
        db.commit()

        # Print Success
        print("[SUCCESS]: DID registered successfully\n")

        return {"status": "DID registered successfully", "tx_hash": tx_hash.hex()}

    except Exception as e:
        logging.error(f"Error in register_did: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/issue_vc/")
def issue_vc(vc_data: VCRequest, db: Session = Depends(get_session)):
    try:
        # Hash email to match with registered user
        email_hash = hashlib.sha256(vc_data.email.encode("utf-8")).hexdigest()

        # Find user by hashed email
        statement = select(User).where(User.email_hash == email_hash)
        user = db.exec(statement).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Issue VC on blockchain
        contract = get_contract()
        txn = contract.functions.issueVC(
            email_hash,
            "http://example.com/context",  # VC context
            vc_data.vc_type,
            "2024-01-01T00:00:00Z",  # Issuance date
            "2025-01-01T00:00:00Z",  # Expiration date (optional)
            vc_data.claims,
            "signature",  # Placeholder for proof/signature
        ).build_transaction(
            {
                "from": account.address,
                "nonce": w3.eth.get_transaction_count(account.address),
                "gas": 6721975,
                "gasPrice": w3.to_wei("1", "gwei"),
            }
        )

        # Sign and send transaction
        signed_txn = w3.eth.account.sign_transaction(txn, private_key=private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        w3.eth.wait_for_transaction_receipt(tx_hash)

        # Update user's VC in the database
        user.vc = f"VC for {vc_data.vc_type} issued"
        db.commit()

        return {"status": "VC issued successfully", "tx_hash": tx_hash.hex()}

    except Exception as e:
        logging.error(f"Error in issue_vc: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/get_user_by_hash/{email_hash}")
def get_user_by_hash(email_hash: str, db: Session = Depends(get_session)):
    try:
        # Find user by hashed email
        statement = select(User).where(User.email_hash == email_hash)
        user = db.exec(statement).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return {"email_hash": user.email_hash, "vc": user.vc}

    except Exception as e:
        logging.error(f"Error in get_user_by_hash: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/verify_vc/")
def verify_vc(email: str, issuance_date: str):
    try:
        # Hash email for verification
        email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()

        # Verify VC on blockchain
        contract = get_contract()
        is_valid = contract.functions.verifyVC(
            "http://example.com/context", email_hash, issuance_date  # VC context
        ).call()

        return {"status": "VC is valid" if is_valid else "VC is not valid"}

    except Exception as e:
        logging.error(f"Error in verify_vc: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/get_all_users", response_model=List[User])
def get_all_users(db: Session = Depends(get_session)):
    try:
        statement = select(User)
        users = db.exec(statement).all()

        if not users:
            raise HTTPException(status_code=404, detail="No users found")

        return users
    except Exception as e:
        logging.error(f"Error in get_all_users: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/total_users")
def get_total_users(db: Session = Depends(get_session)):
    try:
        statement = select(User)
        users = db.exec(statement).all()
        total_users = len(users)

        return {"total_users": total_users}
    except Exception as e:
        logging.error(f"Error in get_total_users: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

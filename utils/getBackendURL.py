from dotenv import load_dotenv
load_dotenv()
import os

def getBackendURL():
  url = os.getenv("BACKEND_API")
  return url
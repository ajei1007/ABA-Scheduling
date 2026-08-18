from dotenv import load_dotenv
load_dotenv()
import os

secret_key = os.getenv("TOKEN")
header = {
  'Authorization':
  f'Bearer {secret_key}'
}

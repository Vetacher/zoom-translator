from openai import AzureOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv('AZURE_OPENAI_KEY'),
    api_version="2024-08-01-preview",
    azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT')
)

print("Checking deployments...")
try:
    deployments = client.models.list()
    print("Available deployments:")
    for d in deployments.data:
        print(f"  - {d.id}")
except Exception as e:
    print(f"Error: {e}")


Step 1: Create a Google Cloud Project

Go to console.cloud.google.com
Click the project dropdown (top left) → New Project
Name it anything (e.g. my-drive-app) → Create

Step 2: Enable the Google Drive API

In your project, go to APIs & Services → Library
Search for Google Drive API → Click it → Enable

Step 3: Create OAuth 2.0 Credentials

Go to APIs & Services → Credentials
Click + Create Credentials → OAuth 2.0 Client ID
If prompted, configure the OAuth Consent Screen first:

Choose External (or Internal if on Google Workspace)
Fill in App name, support email → Save

Back in Create OAuth Client ID:

Application type: Web application
Name it anything
Under Authorized redirect URIs, click + Add URI and enter:

     http://localhost:5000/api/drive/callback

Click Create

Step 4: Copy Your Credentials
A popup shows your credentials. Copy them into your .env:
dotenvGOOGLE_OAUTH_CLIENT_ID=123456789-abc...apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-xxxxx...

Step 5: (Optional) Service Account Setup
Only needed if you chose the Service Account alternative:

Go to Credentials → + Create Credentials → Service Account
Fill in a name → Create and Continue → Done
Click the service account → Keys tab → Add Key → JSON → download the file
Place it at credentials/service_account.json in your project
Share your Google Drive folder with the service account's email (e.g. my-sa@project.iam.gserviceaccount.com)
Paste the folder ID from the Drive URL into GOOGLE_DRIVE_FOLDER_ID

Quick Reference
VariableWhere to find itGOOGLE_OAUTH_CLIENT_IDCredentials popup → Client IDGOOGLE_OAUTH_CLIENT_SECRETCredentials popup → Client SecretGOOGLE_SERVICE_ACCOUNT_FILEPath to downloaded JSON key fileGOOGLE_DRIVE_FOLDER_IDFrom Drive folder URL: drive.google.com/drive/folders/THIS_PART
Once your .env is filled in, click "Connect Google Drive" in your app to complete the OAuth flow.

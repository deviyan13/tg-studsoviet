import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Права, которые мы просим
SCOPES = [
    'https://www.googleapis.com/auth/forms.body',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def main():
    creds = None
    # Если токен уже есть, грузим его
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # Если токена нет или он просрочен
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            # Запускает локальный сервер для авторизации
            creds = flow.run_local_server(port=0)
        
        # Сохраняем токен для бота
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            print("✅ Успешно! Файл token.json создан. Теперь запускай бота.")

if __name__ == '__main__':
    main()
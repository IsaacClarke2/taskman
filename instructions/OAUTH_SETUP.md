# OAuth Setup Guide

Инструкции по получению OAuth credentials для каждого провайдера.

---

## 1. Google Calendar

### Шаги

1. **Открой Google Cloud Console**
   - https://console.cloud.google.com

2. **Создай новый проект**
   - Select Project → New Project
   - Имя: `telegram-ai-assistant` (любое)
   - Create

3. **Включи Google Calendar API**
   - APIs & Services → Library
   - Найди "Google Calendar API"
   - Enable

4. **Настрой OAuth Consent Screen**
   - APIs & Services → OAuth consent screen
   - User Type: External
   - App name: `AI Calendar Assistant`
   - User support email: твой email
   - Scopes: добавь `../auth/calendar.events` и `../auth/calendar.readonly`
   - Test users: добавь свой email для тестирования
   - Save

5. **Создай OAuth Credentials**
   - APIs & Services → Credentials
   - Create Credentials → OAuth Client ID
   - Application type: Web application
   - Name: `Web Client`
   - Authorized redirect URIs:
     ```
     http://localhost:3000/integrations/google/callback
     https://your-domain.com/integrations/google/callback
     ```
   - Create

6. **Скопируй credentials**
   - Client ID → `GOOGLE_CLIENT_ID`
   - Client Secret → `GOOGLE_CLIENT_SECRET`

### Scopes для кода

```python
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]
```

### OAuth URL

```python
from urllib.parse import urlencode

def get_google_auth_url(state: str) -> str:
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": f"{settings.WEBAPP_URL}/integrations/google/callback",
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",  # Для refresh token
        "prompt": "consent",  # Всегда показывать consent screen
        "state": state,
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
```

### Token Exchange

```python
async def exchange_google_code(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": f"{settings.WEBAPP_URL}/integrations/google/callback",
            }
        )
        return response.json()
        # Returns: access_token, refresh_token, expires_in
```

---

## 2. Microsoft Outlook

### Шаги

1. **Открой Azure Portal**
   - https://portal.azure.com

2. **Зарегистрируй приложение**
   - Azure Active Directory → App registrations
   - New registration
   - Name: `AI Calendar Assistant`
   - Supported account types: "Accounts in any organizational directory and personal Microsoft accounts"
   - Redirect URI: Web → `http://localhost:3000/integrations/outlook/callback`
   - Register

3. **Добавь redirect URIs**
   - Authentication → Add URI
   - Добавь production URL: `https://your-domain.com/integrations/outlook/callback`

4. **Создай client secret**
   - Certificates & secrets → New client secret
   - Description: `web-client`
   - Expires: 24 months
   - Add
   - **Сразу скопируй Value** — он показывается только один раз!

5. **Настрой permissions**
   - API permissions → Add a permission
   - Microsoft Graph → Delegated permissions
   - Добавь:
     - `Calendars.ReadWrite`
     - `User.Read`
   - Grant admin consent (если ты админ)

6. **Скопируй credentials**
   - Application (client) ID → `MICROSOFT_CLIENT_ID`
   - Client secret value → `MICROSOFT_CLIENT_SECRET`

### OAuth URL

```python
def get_outlook_auth_url(state: str) -> str:
    params = {
        "client_id": settings.MICROSOFT_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": f"{settings.WEBAPP_URL}/integrations/outlook/callback",
        "response_mode": "query",
        "scope": "offline_access Calendars.ReadWrite User.Read",
        "state": state,
    }
    return f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?{urlencode(params)}"
```

### Token Exchange

```python
async def exchange_outlook_code(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            data={
                "client_id": settings.MICROSOFT_CLIENT_ID,
                "client_secret": settings.MICROSOFT_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": f"{settings.WEBAPP_URL}/integrations/outlook/callback",
                "scope": "offline_access Calendars.ReadWrite User.Read",
            }
        )
        return response.json()
```

### Graph API Base URL

```
https://graph.microsoft.com/v1.0
```

---

## 3. Notion

### Шаги

1. **Открой Notion Integrations**
   - https://www.notion.so/my-integrations

2. **Создай new integration**
   - New integration
   - Name: `AI Calendar Assistant`
   - Associated workspace: твой workspace
   - Type: Public (для OAuth)
   - Submit

3. **Настрой OAuth**
   - В настройках интеграции → OAuth Domain & URIs
   - Redirect URIs:
     ```
     http://localhost:3000/integrations/notion/callback
     https://your-domain.com/integrations/notion/callback
     ```

4. **Скопируй credentials**
   - OAuth client ID → `NOTION_CLIENT_ID`
   - OAuth client secret → `NOTION_CLIENT_SECRET`

### OAuth URL

```python
def get_notion_auth_url(state: str) -> str:
    params = {
        "client_id": settings.NOTION_CLIENT_ID,
        "response_type": "code",
        "owner": "user",
        "redirect_uri": f"{settings.WEBAPP_URL}/integrations/notion/callback",
        "state": state,
    }
    return f"https://api.notion.com/v1/oauth/authorize?{urlencode(params)}"
```

### Token Exchange

```python
async def exchange_notion_code(code: str) -> dict:
    import base64
    
    credentials = base64.b64encode(
        f"{settings.NOTION_CLIENT_ID}:{settings.NOTION_CLIENT_SECRET}".encode()
    ).decode()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.notion.com/v1/oauth/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
            },
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": f"{settings.WEBAPP_URL}/integrations/notion/callback",
            }
        )
        return response.json()
        # Returns: access_token, workspace_id, workspace_name, etc.
```

### API Headers

```python
headers = {
    "Authorization": f"Bearer {access_token}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}
```

---

## 4. Apple Calendar (CalDAV)

### Нет OAuth — используем App-Specific Password

### Инструкция для пользователя

```markdown
## Подключение Apple Calendar

1. Перейдите на https://appleid.apple.com
2. Войдите в свою учётную запись
3. В разделе "Sign-In and Security" выберите "App-Specific Passwords"
4. Нажмите "Generate an app-specific password"
5. Название: "AI Calendar Assistant"
6. Скопируйте сгенерированный пароль
7. Вставьте его ниже вместе с вашим Apple ID email
```

### Подключение в коде

```python
import caldav

def connect_apple_calendar(email: str, app_password: str) -> caldav.DAVClient:
    client = caldav.DAVClient(
        url="https://caldav.icloud.com",
        username=email,
        password=app_password
    )
    
    # Проверяем подключение
    principal = client.principal()
    calendars = principal.calendars()
    
    return client, calendars
```

### UI Form

```tsx
// web/app/integrations/apple-calendar/page.tsx

<form onSubmit={handleSubmit}>
  <Input
    label="Apple ID Email"
    type="email"
    placeholder="your@icloud.com"
    value={email}
    onChange={setEmail}
  />
  
  <Input
    label="App-Specific Password"
    type="password"
    placeholder="xxxx-xxxx-xxxx-xxxx"
    value={password}
    onChange={setPassword}
  />
  
  <Button type="submit">Connect Apple Calendar</Button>
</form>
```

---

## 5. Telegram Bot

### Шаги

1. **Открой @BotFather в Telegram**
   - https://t.me/BotFather

2. **Создай бота**
   - `/newbot`
   - Name: `AI Calendar Assistant`
   - Username: `ai_calendar_assistant_bot` (должен заканчиваться на `bot`)

3. **Получи токен**
   - BotFather пришлёт токен вида `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`
   - Это `TELEGRAM_BOT_TOKEN`

4. **Настрой бота**
   - `/setdescription` — описание бота
   - `/setabouttext` — текст в профиле
   - `/setuserpic` — аватарка

5. **Включи inline mode (опционально)**
   - `/setinline`
   - Placeholder: `Введите текст события...`

6. **Настрой команды**
   - `/setcommands`
   ```
   start - Начать работу
   settings - Настройки
   calendars - Мои календари
   help - Помощь
   ```

### Webhook Setup

```python
# В production используем webhook
async def setup_webhook():
    await bot.set_webhook(
        url=f"{settings.WEBAPP_URL}/api/telegram/webhook",
        secret_token=settings.TELEGRAM_WEBHOOK_SECRET,  # Для верификации
    )
```

---

## Хранение токенов

### Encryption

```python
# api/utils/crypto.py

from cryptography.fernet import Fernet
import json

def get_fernet(encryption_key: str) -> Fernet:
    return Fernet(encryption_key.encode())

def encrypt_credentials(credentials: dict, encryption_key: str) -> str:
    f = get_fernet(encryption_key)
    json_bytes = json.dumps(credentials).encode()
    return f.encrypt(json_bytes).decode()

def decrypt_credentials(encrypted: str, encryption_key: str) -> dict:
    f = get_fernet(encryption_key)
    json_bytes = f.decrypt(encrypted.encode())
    return json.loads(json_bytes)
```

### Генерация ключа

```bash
# Генерация ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Checklist

- [ ] Google Cloud Project создан
- [ ] Google Calendar API включён
- [ ] Google OAuth credentials получены
- [ ] Azure App Registration создан
- [ ] Microsoft Graph permissions настроены
- [ ] Notion Integration создана
- [ ] Telegram Bot создан
- [ ] Все credentials в `.env`
- [ ] Redirect URIs настроены для localhost и production

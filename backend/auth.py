# auth.py - упрощенная версия без bcrypt
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import json
import hashlib
import secrets
from pathlib import Path

# Настройки безопасности
SECRET_KEY = "your-secret-key-change-this-in-production-12345"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 часа

# Путь к файлу с пользователями
USERS_FILE = Path(__file__).parent / "users.json"

# Безопасность
security = HTTPBearer()


def hash_password(password: str) -> str:
    """Простое хеширование пароля (вместо bcrypt)"""
    salt = "humary_salt_2024"  # В продакшене используйте случайную соль
    return hashlib.sha256((password + salt).encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля"""
    return hash_password(plain_password) == hashed_password


def load_users():
    """Загрузка пользователей из файла"""
    if not USERS_FILE.exists():
        # Создаем тестового пользователя
        default_users = {
            "users": {
                "test@example.com": {
                    "email": "test@example.com",
                    "username": "testuser",
                    "password": hash_password("test123"),
                    "created_at": datetime.now().isoformat()
                }
            }
        }
        save_users(default_users)
        return default_users

    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        default_users = {
            "users": {}
        }
        save_users(default_users)
        return default_users


def save_users(users_data):
    """Сохранение пользователей в файл"""
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users_data, f, ensure_ascii=False, indent=2)


def authenticate_user(email: str, password: str):
    """Аутентификация пользователя"""
    try:
        users_data = load_users()
        users = users_data.get("users", {})

        user = users.get(email)
        if not user:
            return False

        if not verify_password(password, user["password"]):
            return False

        return user
    except Exception as e:
        print(f"Authentication error: {e}")
        return False


def create_access_token(data: dict, expires_delta: timedelta = None):
    """Создание JWT токена"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_user(email: str, username: str, password: str):
    """Создание нового пользователя"""
    users_data = load_users()
    users = users_data.get("users", {})

    # Проверяем, существует ли пользователь
    if email in users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже существует"
        )

    # Создаем нового пользователя
    users[email] = {
        "email": email,
        "username": username,
        "password": hash_password(password),
        "created_at": datetime.now().isoformat()
    }

    users_data["users"] = users
    save_users(users_data)

    return users[email]


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Получение текущего пользователя из токена"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный токен"
            )

        users_data = load_users()
        users = users_data.get("users", {})
        user = users.get(email)

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь не найден"
            )

        return user
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный токен"
        )
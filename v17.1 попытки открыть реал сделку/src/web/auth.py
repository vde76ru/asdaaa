"""
Модуль аутентификации с исправленными импортами
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.models import User
from ..core.config import config

# Схемы безопасности
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")
security = HTTPBearer()

# Настройка хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    """Сервис аутентификации"""
    
    def __init__(self):
        self.secret_key = config.JWT_SECRET_KEY
        self.algorithm = config.JWT_ALGORITHM
        self.expire_minutes = config.ACCESS_TOKEN_EXPIRE_MINUTES
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Проверка пароля"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Хеширование пароля"""
        return pwd_context.hash(password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Создание JWT токена"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.expire_minutes)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def get_current_user_from_token(self, token: str, db: Session) -> User:
        """Получение пользователя из токена"""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception
        
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            raise credentials_exception
        return user
    
    async def authenticate_user(self, db: Session, username: str, password: str) -> Optional[User]:
        """
        Аутентификация пользователя
        
        Args:
            db: Сессия базы данных
            username: Имя пользователя
            password: Пароль
            
        Returns:
            User или None если аутентификация не удалась
        """
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return None
        
        # Проверяем пароль
        if not self.verify_password(password, user.hashed_password):
            return None
        
        # Проверяем, активен ли пользователь
        if not user.is_active:
            return None
        
        # Проверяем, не заблокирован ли пользователь
        if user.is_blocked:
            return None
        
        return user

# Создаем экземпляр сервиса
auth_service = AuthService()

# Функции для обратной совместимости
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    return auth_service.create_access_token(data, expires_delta)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return auth_service.verify_password(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return auth_service.get_password_hash(password)

# Dependencies
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Dependency для получения текущего пользователя"""
    return auth_service.get_current_user_from_token(credentials.credentials, db)

def get_current_user_oauth2(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Dependency для OAuth2PasswordBearer"""
    return auth_service.get_current_user_from_token(token, db)
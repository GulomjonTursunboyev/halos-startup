"""
HALOS Payme API Integration
Automated P2P transaction monitoring via Payme API
Based on: https://github.com/sobirjonovs/automated-p2p-transactions
"""
import json
import logging
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PaymeCard:
    """Payme card data"""
    id: str
    name: str
    number: str
    expire: int
    is_active: bool
    owner: str
    balance: int
    is_main: bool
    date: int


@dataclass
class PaymeCheque:
    """Payme transaction (cheque) data"""
    id: str
    create_time: int
    pay_time: int
    cancel_time: int
    state: int
    type: int
    external: bool
    operation: int
    category: Optional[list]
    error: Optional[str]
    description: str  # Comment/izoh
    detail: Optional[str]
    amount: int  # Amount in tiyin (x100)
    currency: int
    commission: int
    account: list
    card: dict
    
    def get_amount_sum(self) -> int:
        """Get amount in so'm"""
        return self.amount // 100
    
    def has_payment_with_comment(self, comment: str, amount: int) -> bool:
        """Check if this cheque matches comment and amount"""
        return self.description == comment and self.amount == amount
    
    def is_income(self) -> bool:
        """Check if this is an incoming payment (kirim)"""
        # type=2 is income, type=1 is expense
        return self.type == 2


class PaymeSession:
    """Simple session storage"""
    def __init__(self):
        self._data: Dict[str, Any] = {}
    
    def store(self, key: str, value: Any):
        self._data[key] = value
    
    def get(self, key: str) -> Any:
        return self._data.get(key)


class PaymeApi:
    """
    Payme API client for automated P2P transaction monitoring
    
    Usage:
        # First time setup (one time only):
        api = PaymeApi()
        api.set_credentials(login='901234567', password='your_password')
        await api.login()
        await api.send_activation_code()
        # Enter SMS code:
        await api.activate('123456')
        await api.register_device()
        device_id = api.get_device()  # Save this!
        cards = await api.get_my_cards()  # Save card IDs!
        
        # Regular usage:
        api = PaymeApi()
        api.set_credentials(login='901234567', password='your_password')
        api.set_device(device_id)
        
        # Get all transactions
        cheques = await api.get_all_cheques()
        
        # Find payment by comment and amount
        payment = await api.find_by_comment('HALOS_ABC123', 15000 * 100)
    """
    
    ENDPOINT_URL = "https://payme.uz/api/"
    USER_AGENT = "Payme API"
    DEVICE_NAME = "Payme API"
    TIMEOUT = 20
    
    # API endpoints
    API_LOGIN_URL = "users.log_in"
    API_SESSION_ACTIVATE_URL = "sessions.activate"
    API_SEND_ACTIVATION_CODE = "sessions.get_activation_code"
    API_REGISTER_DEVICE_URL = "devices.register"
    API_CHEQUE_URL = "cheque.get_all"
    API_CHEQUE_GET_URL = "cheque.get"
    API_GET_CARDS_URL = "cards.get_all"
    
    def __init__(self):
        self.session = PaymeSession()
        self.credentials: Dict[str, str] = {}
        self.api_session: Optional[str] = None
        self.device: Optional[str] = None
        self.is_active_session: bool = False
        self.cheques: List[PaymeCheque] = []
        self._http_session: Optional[aiohttp.ClientSession] = None
    
    async def _get_http_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.TIMEOUT),
                headers={
                    'User-Agent': self.USER_AGENT,
                    'Content-Type': 'text/plain',
                    'Accept': '*/*',
                    'Connection': 'keep-alive'
                }
            )
        return self._http_session
    
    async def close(self):
        """Close HTTP session"""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
    
    async def _post(self, url: str, params: Any, headers: Optional[List[str]] = None) -> Dict:
        """Make POST request to Payme API"""
        session = await self._get_http_session()
        
        payload = {
            'method': url,
            'params': params
        }
        
        request_headers = {}
        if headers:
            for h in headers:
                if ':' in h:
                    key, value = h.split(':', 1)
                    request_headers[key.strip()] = value.strip()
        
        try:
            async with session.post(
                self.ENDPOINT_URL,
                json=payload,
                headers=request_headers
            ) as response:
                # Get API-SESSION from headers
                if 'api-session' in response.headers:
                    self.api_session = response.headers['api-session']
                elif 'API-SESSION' in response.headers:
                    self.api_session = response.headers['API-SESSION']
                
                result = await response.json()
                logger.debug(f"Payme API response: {url} -> {result}")
                return result
                
        except Exception as e:
            logger.error(f"Payme API error: {e}")
            raise
    
    def set_credentials(self, login: str, password: str) -> 'PaymeApi':
        """Set login credentials"""
        self.credentials = {
            'login': login,
            'password': password
        }
        return self
    
    def set_device(self, device: str) -> 'PaymeApi':
        """Set device ID"""
        self.device = device
        return self
    
    def get_device(self) -> Optional[str]:
        """Get device ID"""
        return self.device
    
    async def login(self, extra_headers: Optional[List[str]] = None) -> 'PaymeApi':
        """Login to Payme"""
        headers = extra_headers or []
        if self.device:
            headers.append(f"Device: {self.device}")
        
        await self._post(self.API_LOGIN_URL, self.credentials, headers)
        self.is_active_session = bool(self.device)
        
        logger.info("Payme login successful")
        return self
    
    async def send_activation_code(self) -> 'PaymeApi':
        """Send activation code to phone"""
        await self._post(
            self.API_SEND_ACTIVATION_CODE,
            {},
            [f"API-SESSION: {self.api_session}"]
        )
        logger.info("Activation code sent")
        return self
    
    async def activate(self, code: str) -> 'PaymeApi':
        """Activate session with SMS code"""
        await self._post(
            self.API_SESSION_ACTIVATE_URL,
            {'code': code, 'device': True},
            [f"API-SESSION: {self.api_session}"]
        )
        logger.info("Session activated")
        return self
    
    async def register_device(self) -> 'PaymeApi':
        """Register device"""
        result = await self._post(
            self.API_REGISTER_DEVICE_URL,
            {'display': self.DEVICE_NAME, 'type': 2},
            [f"API-SESSION: {self.api_session}"]
        )
        
        if 'result' in result:
            device_id = result['result']['_id']
            device_key = result['result']['key']
            self.device = f"{device_id}; {device_key};"
            logger.info(f"Device registered: {self.device}")
        
        return self
    
    async def get_my_cards(self) -> List[PaymeCard]:
        """Get all cards"""
        await self.login([f"Device: {self.device}"])
        
        result = await self._post(
            self.API_GET_CARDS_URL,
            {},
            [f"API-SESSION: {self.api_session}", f"Device: {self.device}"]
        )
        
        cards = []
        if 'result' in result and 'cards' in result['result']:
            for card_data in result['result']['cards']:
                card = PaymeCard(
                    id=card_data['_id'],
                    name=card_data['name'],
                    number=card_data['number'],
                    expire=card_data['expire'],
                    is_active=card_data['active'],
                    owner=card_data['owner'],
                    balance=card_data['balance'],
                    is_main=card_data['main'],
                    date=card_data['date']
                )
                cards.append(card)
        
        logger.info(f"Found {len(cards)} cards")
        return cards
    
    async def get_all_cheques(self, sort: Optional[Dict] = None) -> List[PaymeCheque]:
        """Get all transactions (cheques)"""
        sort = sort or {
            'count': 90,
            'group': 'time'
        }
        
        await self.login([f"Device: {self.device}"])
        
        result = await self._post(
            self.API_CHEQUE_URL,
            sort,
            [f"API-SESSION: {self.api_session}", f"Device: {self.device}"]
        )
        
        cheques = []
        if 'result' in result and 'cheques' in result['result']:
            for ch in result['result']['cheques']:
                try:
                    cheque = PaymeCheque(
                        id=ch.get('_id', ''),
                        create_time=ch.get('create_time', 0),
                        pay_time=ch.get('pay_time', 0),
                        cancel_time=ch.get('cancel_time', 0),
                        state=ch.get('state', 0),
                        type=ch.get('type', 0),
                        external=ch.get('external', False),
                        operation=ch.get('operation', 0),
                        category=ch.get('category'),
                        error=ch.get('error'),
                        description=ch.get('description', ''),
                        detail=ch.get('detail'),
                        amount=ch.get('amount', 0),
                        currency=ch.get('currency', 0),
                        commission=ch.get('commission', 0),
                        account=ch.get('account', []),
                        card=ch.get('card', {})
                    )
                    cheques.append(cheque)
                except Exception as e:
                    logger.warning(f"Failed to parse cheque: {e}")
        
        self.cheques = cheques
        logger.info(f"Found {len(cheques)} cheques")
        return cheques
    
    async def select_card(self, card_id: str, sort: Optional[Dict] = None) -> 'PaymeApi':
        """Get transactions for specific card"""
        now = datetime.now()
        default_sort = {
            'card': card_id,
            'count': sort.get('count', 20) if sort else 20,
            'from': sort.get('from') if sort else None,
            'group': sort.get('group', 'time') if sort else 'time',
            'offset': sort.get('offset', 0) if sort else 0,
            'to': sort.get('to') if sort else {
                'day': now.day,
                'month': now.month - 1,  # Payme uses 0-indexed months
                'year': now.year
            }
        }
        
        self.cheques = await self.get_all_cheques(default_sort)
        return self
    
    def find_by_comment(self, comment: str, amount: int = 0) -> List[PaymeCheque]:
        """
        Find payments by comment (izoh)
        
        Args:
            comment: The comment/description to search for
            amount: Amount in tiyin (so'm * 100). If 0, only match by comment.
        
        Returns:
            List of matching cheques
        """
        result = []
        for cheque in self.cheques:
            if amount > 0:
                if cheque.has_payment_with_comment(comment, amount):
                    result.append(cheque)
            else:
                if cheque.description == comment:
                    result.append(cheque)
        
        return result
    
    def find_by_amount(self, amount: int, is_income: bool = True) -> List[PaymeCheque]:
        """
        Find payments by amount
        
        Args:
            amount: Amount in tiyin (so'm * 100)
            is_income: If True, only find incoming payments
        
        Returns:
            List of matching cheques
        """
        result = []
        for cheque in self.cheques:
            if cheque.amount == amount:
                if is_income and not cheque.is_income():
                    continue
                result.append(cheque)
        
        return result
    
    def find_recent_income(self, min_amount: int = 0, minutes: int = 30) -> List[PaymeCheque]:
        """
        Find recent incoming payments
        
        Args:
            min_amount: Minimum amount in tiyin
            minutes: Look back this many minutes
        
        Returns:
            List of recent incoming payments
        """
        cutoff_time = (datetime.now() - timedelta(minutes=minutes)).timestamp() * 1000
        
        result = []
        for cheque in self.cheques:
            if cheque.is_income() and cheque.amount >= min_amount:
                if cheque.create_time >= cutoff_time:
                    result.append(cheque)
        
        return result


# ==================== PAYME CONFIG ====================
# You need to fill these after first-time setup

PAYME_CONFIG = {
    "enabled": False,  # Set to True after getting device_id and card_id
    "login": "973710506",  # Payme phone number
    "password": "Gulomboy0506",  # Payme password
    "device_id": "",  # Get from setup_payme.py
    "card_id": "",  # Get from setup_payme.py
    "check_interval_seconds": 30,  # How often to check for new payments
}


# ==================== GLOBAL PAYME INSTANCE ====================
_payme_api: Optional[PaymeApi] = None


async def get_payme_api() -> Optional[PaymeApi]:
    """Get or create Payme API instance"""
    global _payme_api
    
    if not PAYME_CONFIG["enabled"]:
        return None
    
    if _payme_api is None:
        _payme_api = PaymeApi()
        _payme_api.set_credentials(
            login=PAYME_CONFIG["login"],
            password=PAYME_CONFIG["password"]
        )
        _payme_api.set_device(PAYME_CONFIG["device_id"])
    
    return _payme_api


async def check_payme_payment(comment: str, amount_sum: int) -> Optional[PaymeCheque]:
    """
    Check if payment exists in Payme
    
    Args:
        comment: Payment comment (e.g., "HALOS_ABC123")
        amount_sum: Amount in so'm
    
    Returns:
        PaymeCheque if found, None otherwise
    """
    api = await get_payme_api()
    if not api:
        return None
    
    try:
        # Get recent cheques
        if PAYME_CONFIG["card_id"]:
            await api.select_card(PAYME_CONFIG["card_id"])
        else:
            await api.get_all_cheques()
        
        # Find by comment and amount (amount in tiyin)
        matches = api.find_by_comment(comment, amount_sum * 100)
        
        if matches:
            logger.info(f"Found payment: {comment}, {amount_sum} so'm")
            return matches[0]
        
        return None
        
    except Exception as e:
        logger.error(f"Error checking Payme payment: {e}")
        return None


async def check_payme_payment_by_amount(amount_sum: int, tolerance: int = 0) -> Optional[PaymeCheque]:
    """
    Check if payment exists by amount only
    
    Args:
        amount_sum: Amount in so'm
        tolerance: Allow +/- this amount
    
    Returns:
        PaymeCheque if found, None otherwise
    """
    api = await get_payme_api()
    if not api:
        return None
    
    try:
        # Get recent cheques
        await api.get_all_cheques({'count': 50, 'group': 'time'})
        
        # Find recent income
        for cheque in api.find_recent_income(min_amount=(amount_sum - tolerance) * 100, minutes=60):
            if tolerance > 0:
                if abs(cheque.get_amount_sum() - amount_sum) <= tolerance:
                    return cheque
            else:
                if cheque.get_amount_sum() == amount_sum:
                    return cheque
        
        return None
        
    except Exception as e:
        logger.error(f"Error checking Payme payment: {e}")
        return None

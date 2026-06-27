from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class Product:
    name: str
    brand: str  # 'zara' | 'stradivarius'
    url: str
    size: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    external_id: Optional[str] = None


@dataclass
class ScrapeResult:
    product_id: str
    timestamp: datetime
    success: bool
    status_code: Optional[int] = None
    in_stock: Optional[bool] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    # '403' | '429' | '503' | 'captcha' | 'perimeterx' | 'akamai_challenge' | 'cloudflare' | None
    ban_signal: Optional[str] = None
    error_message: Optional[str] = None
    response_time_ms: Optional[int] = None


@dataclass
class BanEvent:
    product_id: str
    signal_type: str
    details: str
    timestamp: datetime = field(default_factory=lambda: datetime.utcnow())
    recovery_timestamp: Optional[datetime] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

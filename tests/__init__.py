from dataclasses import dataclass
from typing import Optional, Type, Union
from unittest.mock import DEFAULT, _Sentinel


@dataclass
class TestConfig:
    url: Optional[str] = None
    installer: Optional[str] = None
    extras: Union[str, None, Type[_Sentinel]] = DEFAULT
    version: Optional[str] = None
    verbose: bool = False
    rev: Optional[str] = None

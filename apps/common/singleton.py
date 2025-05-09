"""单例模式"""

import threading
from typing import Any, ClassVar


class SingletonMeta(type):
    """单例元类"""

    _instances: ClassVar[dict[type, Any]] = {}
    """单例实例字典"""
    _lock: ClassVar[threading.RLock] = threading.RLock()
    """可重入锁"""

    def __call__(cls, *args, **kwargs):  # noqa: ANN002, ANN003, ANN204
        """获取单例"""
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
            return cls._instances[cls]

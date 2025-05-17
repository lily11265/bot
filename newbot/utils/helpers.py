# utils/helpers.py
from typing import Dict, Any, Union, Optional

def update_nested_dict(original: Dict, updates: Dict) -> Dict:
    """중첩 딕셔너리 업데이트 (깊은 병합)"""
    for key, value in updates.items():
        if isinstance(value, dict) and key in original and isinstance(original[key], dict):
            update_nested_dict(original[key], value)
        else:
            original[key] = value
    return original

def safe_int_convert(value: Any, default: int = 0) -> int:
    """
    안전하게 정수로 변환
    
    Args:
        value (Any): 변환할 값
        default (int): 기본값
        
    Returns:
        int: 변환된 정수 또는 기본값
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def safe_float_convert(value: Any, default: float = 0.0) -> float:
    """
    안전하게 실수로 변환
    
    Args:
        value (Any): 변환할 값
        default (float): 기본값
        
    Returns:
        float: 변환된 실수 또는 기본값
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def format_time(seconds: int) -> str:
    """
    초를 HH:MM:SS 형식으로 변환
    
    Args:
        seconds (int): 초
        
    Returns:
        str: 포맷된 시간 문자열
    """
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    
    if hours > 0:
        return f"{hours}시간 {minutes}분 {seconds}초"
    elif minutes > 0:
        return f"{minutes}분 {seconds}초"
    else:
        return f"{seconds}초"
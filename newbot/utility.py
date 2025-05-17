import discord
import json
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import time
import re
import random
import logging
from typing import Dict, Any, Union, Optional, List, Tuple

# 디버그 모드 설정 (전역 변수)
DEBUG_MODE = True
VERBOSE_DEBUG = True

# 로깅 설정
logger = logging.getLogger('discord_bot')

# Google Sheets API 설정
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = 'credentials.json'
PLAYER_SPREADSHEET_ID = '1YeP2ElmBm0IliaKB0jGW4nQw1pxHnPC9dOgDMLthldA'

# NPC 유저 목록
NPC_USERS = {
    "system | 시스템": "1007172975222603798",
    "센트 커뮤계": "1154811209657364510",
    "오슈아": "741239455305957437",
    "우캬": "1193931901250060401",
    "인계": "1193511011450359808",
    "찐따아찌": "691363195192868957",
    "차차": "509276839605174272",
    "똥갱 커뮤계": "1232712146379477075",
    "라따뚜이": "512198090342662154",
    "릴리": "1090546247770832910",
    "멈듀": "478242229492908039",
    "솜": "1265935441039720449",
    "에르가": "1036495439656124436",
    "용쓰": "628582017529020426",
    "잉기디 네온": "1127398721529843712",
    "조옆학": "713996804873650207",
    "폿포이": "803160496089858098",
    "선장": "416984019465666560",
    "꿀유자차": "278518685713563649",
    "당신의 맘을 back get some me down" : "1109468989119279285"
}

PLAYER_USERS = {
    "릴리 부계" : "1093419776266743838",
    "lily" : "300661054541660160"
}

# 효과별 주사위 제한
EFFECT_DICE_RESTRICTIONS = {
    "저주": {"type": "fixed", "value": 1},
    "콩": {"type": "fixed", "value": 22},
}

# 효과별 주사위 최대값 보정
DICE_MAX_MODIFIERS = {
    "축복": 50,    # +50 (1d150)
    "커피": 10,    # +10 (1d110)  
    "취함": -30,   # -30 (1d70)
    "만취": -50,   # -50 (1d50)
}

#######################
# 로깅 관련 함수들
#######################

def setup_logger(log_file: str = 'bot_log.log', debug_mode: bool = True, verbose: bool = True, log_to_file: bool = True) -> None:
    """
    로깅 설정 초기화
    
    Args:
        log_file (str): 로그 파일 경로
        debug_mode (bool): 디버그 모드 여부
        verbose (bool): 상세 로깅 여부
        log_to_file (bool): 파일 로깅 여부
    """
    global DEBUG_MODE, VERBOSE_DEBUG
    DEBUG_MODE = debug_mode
    VERBOSE_DEBUG = verbose
    
    # 로거 가져오기
    log = logging.getLogger('discord_bot')
    
    # 로거 레벨 설정
    log.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    
    # 이미 핸들러가 있는지 확인
    if log.handlers:
        log_debug("로거 핸들러가 이미 설정되어 있습니다. 설정만 업데이트합니다.", False)
        return
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    log.addHandler(console_handler)
    
    # 파일 로깅
    if log_to_file:
        file_handler = logging.FileHandler(filename=log_file, encoding='utf-8', mode='a')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        log.addHandler(file_handler)
    
    log_info(f"로깅 설정 완료: 디버그={debug_mode}, 상세={verbose}, 파일로깅={log_to_file}")

def log_debug(message: str, verbose: bool = False) -> None:
    """
    디버그 로그 출력 함수
    
    Args:
        message (str): 로그 메시지
        verbose (bool): 상세 로그 여부
    """
    if DEBUG_MODE:
        if not verbose or (verbose and VERBOSE_DEBUG):
            logger.debug(message)

def log_info(message: str) -> None:
    """정보 로그 출력 함수"""
    logger.info(message)

def log_warning(message: str) -> None:
    """경고 로그 출력 함수"""
    logger.warning(message)

def log_error(message: str, exc_info: Optional[Exception] = None) -> None:
    """
    에러 로그 출력 함수
    
    Args:
        message (str): 에러 메시지
        exc_info (Exception, optional): 예외 정보
    """
    if exc_info:
        logger.error(message, exc_info=True)
    else:
        logger.error(message)

#######################
# 파일 처리 관련 함수들
#######################

def load_json(file_path: str, default: Dict = None) -> Dict:
    """
    JSON 파일 로드 (json 폴더 내에서 로드)
    
    Args:
        file_path (str): 파일 경로
        default (Dict, optional): 기본값
        
    Returns:
        Dict: 로드된 데이터
    """
    if default is None:
        default = {}
    
    try:
        # 원본 파일 경로에서 디렉토리와 파일명 분리
        file_dir = os.path.dirname(os.path.abspath(file_path))
        file_name = os.path.basename(file_path)
        
        # json 폴더 내 파일 경로 구성
        json_dir = os.path.join(file_dir, 'json')
        json_file_path = os.path.join(json_dir, file_name)
        
        # 실제 확인할 파일 경로 (우선적으로 json 폴더 내 파일 확인)
        actual_file_path = json_file_path if os.path.exists(json_file_path) else file_path
        
        if os.path.exists(actual_file_path):
            encodings = ['utf-8', 'utf-8-sig', 'cp949', 'euc-kr']
            for encoding in encodings:
                try:
                    with open(actual_file_path, 'r', encoding=encoding) as f:
                        return json.load(f)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
            # a모든 인코딩을 시도해도 실패하면 경고 로그
            log_warning(f"파일을 읽을 수 없습니다 (인코딩 문제): {actual_file_path}. 기본값 반환.")
            return default
        else:
            log_warning(f"파일이 존재하지 않습니다: {file_path} (json 폴더 내 {json_file_path}). 기본값 반환.")
            return default
    except Exception as e:
        log_error(f"JSON 파일 로드 중 오류: {e}", e)
        return default

def save_json(file_path: str, data: Dict, indent: int = 2) -> bool:
    """
    JSON 파일 저장 (json 폴더 내에 저장)
    
    Args:
        file_path (str): 파일 경로 (파일명만 제공시 json 폴더에 저장)
        data (Dict): 저장할 데이터
        indent (int): 들여쓰기 크기
        
    Returns:
        bool: 성공 여부
    """
    try:
        # json 폴더 경로 생성
        json_dir = os.path.join(os.path.dirname(os.path.abspath(file_path)), 'json')
        
        # 파일명만 추출
        file_name = os.path.basename(file_path)
        
        # json 폴더가 없으면 생성
        if not os.path.exists(json_dir):
            os.makedirs(json_dir)
        
        # json 폴더 내에 파일 경로 설정
        json_file_path = os.path.join(json_dir, file_name)
        
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        return True
    except Exception as e:
        log_error(f"JSON 파일 저장 중 오류: {e}", e)
        return False

def update_nested_dict(original: Dict, updates: Dict) -> Dict:
    """
    중첩 딕셔너리 업데이트 (깊은 병합)
    
    Args:
        original (Dict): 원본 딕셔너리
        updates (Dict): 업데이트할 딕셔너리
        
    Returns:
        Dict: 업데이트된 딕셔너리
    """
    for key, value in updates.items():
        if isinstance(value, dict) and key in original and isinstance(original[key], dict):
            update_nested_dict(original[key], value)
        else:
            original[key] = value
    return original

#######################
# 데이터 변환 관련 함수들
#######################

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

#######################
# 플레이어 관련 함수들
#######################

def get_pure_name(nickname):
    """효과가 붙은 닉네임에서 순수 닉네임만 추출"""
    if '[' in nickname and ']' in nickname:
        start = nickname.find('[')
        end = nickname.find(']') + 1
        before_bracket = nickname[:start].strip()
        after_bracket = nickname[end:].strip()
        
        if before_bracket:
            return before_bracket
        elif after_bracket:
            return after_bracket
        else:
            return nickname.strip()
    return nickname.strip()

def get_all_effects(player):
    """모든 효과 파일에서 플레이어의 효과를 수집"""
    all_effects = []
    player_id = str(player.id)
    
    # 닉네임에서 효과 추출
    match = re.match(r'^\[(.*?)\](.*)', player.display_name)
    if match:
        effects_str = match.group(1)
        nick_effects = [e.strip() for e in effects_str.split(',')]
        all_effects.extend(nick_effects)
    
    # effects_data.json 확인
    effects_data = load_json('effects_data.json')
    if effects_data and player_id in effects_data:
        for effect_name in effects_data[player_id].keys():
            if effect_name not in all_effects:
                all_effects.append(effect_name)
    
    # cafe_effects.json 확인
    cafe_effects = load_json('cafe_effects.json')
    if cafe_effects and player_id in cafe_effects:
        for effect_name in cafe_effects[player_id].keys():
            if effect_name not in all_effects:
                all_effects.append(effect_name)
    
    # drink_states.json 확인
    drink_states = load_json('drink_states.json')
    if drink_states and player_id in drink_states:
        drink_level = drink_states[player_id].get('level', 0)
        if drink_level >= 8:
            if '만취' not in all_effects:
                all_effects.append('만취')
        elif drink_level >= 4:
            if '취함' not in all_effects:
                all_effects.append('취함')
    
    # daily_effects.json 확인
    daily_effects = load_json('daily_effects.json')
    if daily_effects and player_id in daily_effects:
        for effect_name in daily_effects[player_id].keys():
            if effect_name not in all_effects:
                all_effects.append(effect_name)
    
    return all_effects

def is_npc_user(player):
    """플레이어가 NPC인지 확인 (ID 또는 닉네임으로)"""
    # ID로 확인
    player_id_str = str(player.id)
    if player_id_str in NPC_USERS.values():
        return True
    
    # 순수 닉네임으로 확인 (효과가 붙은 경우 제거)
    pure_nickname = get_pure_name(player.display_name)
    if pure_nickname in NPC_USERS.keys():
        return True
    
    # NPC 역할 확인
    if any(role.name == "NPC" for role in player.roles):
        return True
    
    return False

async def get_player_balance(player_name: str) -> Tuple[Optional[int], Optional[str]]:
    """
    플레이어의 현재 코인 잔액을 조회합니다.
    
    Args:
        player_name (str): 플레이어 이름 또는 닉네임
        
    Returns:
        Tuple[Optional[int], Optional[str]]: (잔액, 오류 메시지) 형태. 성공 시 (잔액, None), 실패 시 (None, 오류)
    """
    try:
        # 순수 이름 추출 (효과 등이 포함된 경우 제거)
        pure_name = get_pure_name(player_name)
        
        # 구글 시트 접근
        creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, SCOPES)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(PLAYER_SPREADSHEET_ID)
        
        # "러너 시트" 워크시트 선택
        runner_sheet = sheet.worksheet("러너 시트")
        
        # 모든 유저 이름 가져오기 (B14:B39)
        users = runner_sheet.get('B14:B39')
        
        # 플레이어 이름 찾기
        row_idx = None
        for idx, user in enumerate(users):
            if user and user[0].strip() == pure_name:
                row_idx = idx + 14  # 시트에서의 실제 행 번호
                break
        
        if row_idx is None:
            return None, f"플레이어 '{pure_name}'을(를) 찾을 수 없습니다."
        
        # 잔액 가져오기 (D열)
        balance = runner_sheet.acell(f'D{row_idx}').value
        
        if not balance or not balance.isdigit():
            return 0, "잔액이 설정되지 않았습니다."
        
        return int(balance), None
    except Exception as e:
        log_error(f"잔액 확인 중 오류 발생: {e}", e)
        return None, f"잔액 확인 중 오류: {e}"

async def update_player_balance(player_name: str, amount_change: int) -> Tuple[bool, Union[Dict, str]]:
    """
    플레이어의 코인 잔액을 업데이트합니다.
    
    Args:
        player_name (str): 플레이어 이름 또는 닉네임
        amount_change (int): 변경할 금액 (양수: 증가, 음수: 감소)
        
    Returns:
        Tuple[bool, Union[Dict, str]]: (성공 여부, 결과). 성공 시 (True, 변경 정보), 실패 시 (False, 오류 메시지)
    """
    try:
        # 순수 이름 추출 (효과 등이 포함된 경우 제거)
        pure_name = get_pure_name(player_name)
        
        # 현재 잔액 가져오기
        current_balance, error = await get_player_balance(pure_name)
        
        if error:
            return False, error
        
        # 새 잔액 계산
        new_balance = current_balance + amount_change
        
        # 음수 방지 (옵션)
        if new_balance < 0:
            new_balance = 0
            amount_change = -current_balance
        
        # 구글 시트 접근
        creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, SCOPES)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(PLAYER_SPREADSHEET_ID)
        
        # "러너 시트" 워크시트 선택
        runner_sheet = sheet.worksheet("러너 시트")
        
        # 모든 유저 이름 가져오기 (B14:B39)
        users = runner_sheet.get('B14:B39')
        
        # 플레이어 이름 찾기
        row_idx = None
        for idx, user in enumerate(users):
            if user and user[0].strip() == pure_name:
                row_idx = idx + 14  # 시트에서의 실제 행 번호
                break
        
        if row_idx is None:
            return False, f"플레이어 '{pure_name}'을(를) 찾을 수 없습니다."
        
        # 잔액 업데이트 (D열)
        runner_sheet.update_cell(row_idx, 4, new_balance)
        
        log_info(f"플레이어 '{pure_name}'의 잔액 업데이트: {current_balance} → {new_balance} ({amount_change:+})")
        
        return True, {
            "old": current_balance,
            "new": new_balance,
            "change": amount_change
        }
    except Exception as e:
        log_error(f"잔액 업데이트 중 오류 발생: {e}", e)
        return False, f"잔액 업데이트 중 오류: {e}"

#######################
# 쿨타임 관련 함수들
#######################

def load_cooldowns(cooldown_file):
    """쿨타임 데이터 로드"""
    return load_json(cooldown_file, {})

def save_cooldowns(cooldowns, cooldown_file):
    """쿨타임 데이터 저장"""
    save_json(cooldown_file, cooldowns)

def check_cooldown(cooldowns, user_id, cooldown_duration):
    """유저의 쿨타임 확인"""
    user_id = str(user_id)
    if user_id in cooldowns:
        last_used = cooldowns[user_id]
        now = time.time()
        if now - last_used < cooldown_duration:
            remaining = int(cooldown_duration - (now - last_used))
            minutes, seconds = divmod(remaining, 60)
            return False, f"{minutes}분 {seconds}초 후에 다시 시도할 수 있습니다."
    return True, None

def set_cooldown(cooldowns, user_id):
    """유저의 쿨타임 설정"""
    cooldowns[str(user_id)] = time.time()

def check_cooldown_extended(last_time: int, cooldown: int) -> Tuple[bool, int]:
    """
    쿨타임 확인 (확장 버전)
    
    Args:
        last_time (int): 마지막 실행 시간 (타임스탬프)
        cooldown (int): 쿨타임 (초)
        
    Returns:
        Tuple[bool, int]: (쿨타임 완료 여부, 남은 시간)
    """
    current_time = int(time.time())
    elapsed = current_time - last_time
    
    if elapsed >= cooldown:
        return True, 0
    else:
        return False, cooldown - elapsed

#######################
# 인벤토리 관련 함수들
#######################

async def add_item_to_inventory(player_name, item):
    """플레이어 인벤토리에 아이템 추가 - 중복 아이템은 카운트만 증가"""
    try:
        # 구글 시트 연결
        creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, SCOPES)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(PLAYER_SPREADSHEET_ID)
        
        # "러너 시트" 워크시트 선택
        runner_sheet = sheet.worksheet("러너 시트")
        
        # 순수 이름으로 플레이어 찾기
        pure_name = get_pure_name(player_name)
        users = runner_sheet.get('B14:B39')
        
        row_idx = None
        for idx, user in enumerate(users):
            if user and user[0].strip() == pure_name:
                row_idx = idx + 14  # 시트에서의 실제 행 번호
                break
        
        if row_idx is None:
            log_warning(f"인벤토리 업데이트 실패: 플레이어 '{pure_name}'를 찾을 수 없습니다.")
            return False, "플레이어를 찾을 수 없습니다."
        
        # 현재 인벤토리 가져오기
        inventory = runner_sheet.acell(f'G{row_idx}').value
        
        # 인벤토리가 비어있는 경우
        if not inventory or inventory.strip() == "":
            # 새 아이템 추가
            new_item_entry = f"{item['name']}"
            runner_sheet.update_cell(row_idx, 7, new_item_entry)
            log_info(f"인벤토리 업데이트: '{pure_name}'에게 첫 아이템 '{item['name']}' 추가됨")
            return True, None
        
        # 기존 인벤토리에서 아이템 검색
        item_exists = False
        updated_inventory = []
        
        # 인벤토리 아이템 파싱
        inventory_items = inventory.split(', ')
        
        for inv_item in inventory_items:
            # 기본 이름만 있는 경우 vs 개수가 표시된 경우 구분
            base_name = inv_item
            count = 1
            
            # "아이템명(n개)" 형식 확인
            if '개)' in inv_item:
                # 마지막 괄호 찾기
                last_bracket_start = inv_item.rfind('(')
                last_bracket_end = inv_item.rfind(')')
                
                if last_bracket_start != -1 and last_bracket_end != -1:
                    count_text = inv_item[last_bracket_start+1:last_bracket_end]
                    if count_text.endswith('개'):
                        try:
                            count = int(count_text[:-1])  # '개' 제외한 숫자 부분
                            base_name = inv_item[:last_bracket_start]  # 괄호 앞 부분
                        except ValueError:
                            # 숫자로 변환 실패시 기본값 유지
                            pass
            
            # 아이템 이름 비교 (기본 이름만)
            if base_name == item['name']:
                # 같은 아이템 찾음 - 카운트 증가
                item_exists = True
                updated_inventory.append(f"{base_name}({count+1}개)")
            else:
                # 다른 아이템은 그대로 유지
                updated_inventory.append(inv_item)
        
        # 기존 인벤토리에 없는 경우 새로 추가
        if not item_exists:
            updated_inventory.append(f"{item['name']}")
        
        # 업데이트된 인벤토리 저장
        updated_inventory_str = ", ".join(updated_inventory)
        runner_sheet.update_cell(row_idx, 7, updated_inventory_str)
        
        log_info(f"인벤토리 업데이트: '{pure_name}'에게 아이템 '{item['name']}' 추가됨 (중복: {item_exists})")
        return True, None
    except Exception as e:
        log_error(f"인벤토리 업데이트 중 오류 발생: {e}", e)
        return False, f"인벤토리 업데이트 중 오류: {e}"

async def check_requirement(player_name, requirement_type, requirement_value):
    """요구사항 확인 (호감도 또는 아이템)"""
    try:
        pure_name = get_pure_name(player_name)  # 순수 이름 추출
        
        if requirement_type == "호감도":
            # 호감도 확인 로직
            # affection.py에서 가져온 get_feeling 함수 사용
            import file.affection
            feelings = await file.affection.get_feeling(pure_name, requirement_value.split(':')[0])
            if feelings and len(feelings) > 0:
                required_level = int(requirement_value.split(':')[1])
                return feelings[0]["feeling"] >= required_level
            return False
        
        elif requirement_type == "아이템":
            # 아이템 소유 확인 로직
            creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, SCOPES)
            client = gspread.authorize(creds)
            sheet = client.open_by_key(PLAYER_SPREADSHEET_ID)
            
            runner_sheet = sheet.worksheet("러너 시트")
            
            users = runner_sheet.get('B14:B39')
            
            row_idx = None
            for idx, user in enumerate(users):
                if user and user[0].strip() == pure_name:
                    row_idx = idx + 14
                    break
            
            if row_idx is None:
                log_warning(f"요구사항 확인 실패: 플레이어 '{pure_name}'를 찾을 수 없습니다.")
                return False
            
            inventory = runner_sheet.acell(f'G{row_idx}').value
            
            if not inventory:
                return False
            
            # 인벤토리에서 아이템 찾기
            inventory_items = inventory.split(', ')
            for item in inventory_items:
                base_name = item
                
                # 괄호가 있는 경우 기본 이름만 추출
                if '(' in item:
                    base_name = item.split('(')[0]
                
                if base_name.strip() == requirement_value:
                    return True
            
            return False
        
        return False
    except Exception as e:
        log_error(f"요구사항 확인 중 오류 발생: {e}", e)
        return False

async def update_player_health(player_name, health_change):
    """플레이어 체력 업데이트"""
    try:
        # 구글 시트 연결
        creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, SCOPES)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(PLAYER_SPREADSHEET_ID)
        
        # "러너 시트" 워크시트 선택
        runner_sheet = sheet.worksheet("러너 시트")
        
        # 순수 이름으로 플레이어 찾기
        pure_name = get_pure_name(player_name)
        users = runner_sheet.get('B14:B39')
        
        row_idx = None
        for idx, user in enumerate(users):
            if user and user[0].strip() == pure_name:
                row_idx = idx + 14  # 시트에서의 실제 행 번호
                break
        
        if row_idx is None:
            log_warning(f"체력 업데이트 실패: 플레이어 '{pure_name}'를 찾을 수 없습니다.")
            return False, "플레이어를 찾을 수 없습니다."
        
        # 현재 체력 가져오기 (C열, 3번째 열)
        current_health = runner_sheet.acell(f'C{row_idx}').value
        
        # 체력 계산
        if current_health and current_health.isdigit():
            new_health = int(current_health) + health_change
            # 체력은 0 미만이 되지 않도록
            new_health = max(0, new_health)
        else:
            new_health = max(0, health_change)  # 기본값 0에서 시작
        
        # 업데이트된 체력 저장
        runner_sheet.update_cell(row_idx, 3, str(new_health))
        
        log_info(f"체력 업데이트: '{pure_name}'의 체력 {health_change:+d} ({current_health or 0} → {new_health})")
        return True, {
            "previous": int(current_health) if current_health and current_health.isdigit() else 0,
            "new": new_health,
            "change": health_change
        }
    except Exception as e:
        log_error(f"체력 업데이트 중 오류 발생: {e}", e)
        return False, f"체력 업데이트 중 오류: {e}"

async def apply_item_effects(bot, player_discord, item):
    """아이템 효과 적용 (체력 변화 및 효과 부여)"""
    player_name = player_discord.display_name
    item_name = item['name']
    item_desc = item['description']
    
    effects_applied = []
    
    # 1. 체력 변화 체크 - 아이템 이름에서 (숫자) 패턴 찾기
    health_pattern = r'\(([+-]?\d+)\)'
    health_match = re.search(health_pattern, item_name)
    
    if health_match:
        health_change = int(health_match.group(1))
        success, result = await update_player_health(player_name, health_change)
        
        if success:
            change_text = "증가" if health_change > 0 else "감소"
            effects_applied.append(f"체력이 {abs(health_change)} {change_text}했습니다. ({result['previous']} → {result['new']})")
    
    # 2. 효과 부여 체크 - 더 유연한 패턴 사용
    # 여러 가능한 패턴들을 시도
    effect_patterns = [
        r'\[(.*?)\]\s*효과를 얻습니다',  # 공백을 허용하고 마침표는 선택적
        r'\[(.*?)\]효과를 얻습니다',     # 공백 없는 버전
        r'\[(.*?)\]\s*효과를\s*얻습니다', # 중간에도 공백 허용
        r'\[(.*?)\]\s*효과가\s*부여됩니다', # 다른 표현도 허용
    ]
    
    effect_name = None
    for pattern in effect_patterns:
        effect_match = re.search(pattern, item_desc)
        if effect_match:
            effect_name = effect_match.group(1).strip()
            log_debug(f"발견된 효과: '{effect_name}' (패턴: {pattern})")
            break
    
    if effect_name:
        # effect.py의 기능 사용
        try:
            # EffectCommands 가져오기
            effect_cog = bot.get_cog('EffectCommands')
            if effect_cog:
                log_debug(f"EffectCommands cog 발견, 효과 '{effect_name}' 적용 시도")
                
                # 현재 닉네임 가져오기
                current_nickname = player_discord.display_name
                log_debug(f"현재 닉네임: '{current_nickname}'")
                
                # 효과 추가 (24시간)
                expiry_time = datetime.datetime.now().timestamp() + (24 * 60 * 60)
                new_nickname = effect_cog.add_effect(current_nickname, effect_name, player_discord.id, expiry_time)
                log_debug(f"새 닉네임: '{new_nickname}'")
                
                # 닉네임 변경
                if new_nickname != current_nickname:
                    await player_discord.edit(nick=new_nickname)
                    effect_cog.save_effects_data()
                    effects_applied.append(f"[{effect_name}] 효과를 얻었습니다. (24시간 지속)")
                    log_info(f"효과 적용 성공: 플레이어 '{player_name}'에게 '{effect_name}' 효과 적용")
                else:
                    log_debug(f"효과 '{effect_name}'는 이미 적용되어 있습니다.")
                    effects_applied.append(f"[{effect_name}] 효과는 이미 적용되어 있습니다.")
            else:
                log_warning("EffectCommands cog을 찾을 수 없습니다.")
        except Exception as e:
            log_error(f"효과 적용 중 오류 발생: {type(e).__name__}: {e}", e)
    else:
        log_debug(f"아이템 설명에서 효과를 찾을 수 없습니다: '{item_desc}'")
    
    return effects_applied

#######################
# 주사위 관련 함수들
#######################

def get_dice_value_by_effect(player):
    """플레이어의 모든 효과를 확인하여 주사위 값 결정"""
    # 모든 효과 수집
    effects = get_all_effects(player)
    
    # 고정값/특정 범위 효과가 있는지 먼저 확인
    for effect in effects:
        if effect in EFFECT_DICE_RESTRICTIONS:
            restriction = EFFECT_DICE_RESTRICTIONS[effect]
            
            if restriction["type"] == "fixed":
                return restriction["value"]
            elif restriction["type"] == "range":
                return random.randint(restriction["min"], restriction["max"])
            elif restriction["type"] == "fixed_list":
                return random.choice(restriction["values"])
    
    # 주사위 최대값 보정 계산
    base_max = 100
    total_modifier = 0
    
    for effect in effects:
        if effect in DICE_MAX_MODIFIERS:
            total_modifier += DICE_MAX_MODIFIERS[effect]
    
    # 최종 최대값 계산 (최소 1)
    final_max = max(1, base_max + total_modifier)
    
    # 주사위 굴리기
    return random.randint(1, final_max)

#######################
# 스프레드시트 관련 함수들
#######################

async def load_dice_item_mapping_from_sheet(spreadsheet_id, sheet_name, location_ranges, dice_items_file):
    """스프레드시트에서 장소별 주사위값-아이템 맵핑 로드"""
    try:
        # 구글 시트 연결
        creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, SCOPES)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(spreadsheet_id)
        
        # 시트 선택 or 생성
        try:
            dice_sheet = sheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            # 시트 생성
            dice_sheet = sheet.add_worksheet(title=sheet_name, rows=101, cols=15)
            
            # 헤더 추가 (각 장소별로)
            for range_info in location_ranges.values():
                start_col = range_info["start_col"]
                end_col = range_info["end_col"]
                dice_sheet.update(f'{start_col}1:{end_col}1', 
                                  [['주사위 값', '아이템 이름', '아이템 설명']])
            
            # 기본값으로 주사위 1-100 채우기 (각 장소별로)
            for i in range(1, 101):
                for range_info in location_ranges.values():
                    dice_sheet.update(f'{range_info["start_col"]}{i+1}', i)
        
        # 모든 데이터 가져오기
        all_data = dice_sheet.get_all_values()
        
        # 장소별 맵핑 초기화
        location_mapping = {location: {} for location in location_ranges.keys()}
        
        # 각 장소별로 데이터 처리
        for location, range_info in location_ranges.items():
            start_col_index = ord(range_info["start_col"]) - ord('A')
            
            # 헤더 제외한 데이터 처리 (2행부터 101행까지)
            for row_idx in range(1, 101):  # 헤더 제외
                if row_idx < len(all_data):
                    row = all_data[row_idx]
                    
                    if len(row) > start_col_index:  # 해당 열이 존재하는지 확인
                        dice_value_col = row[start_col_index].strip()
                        
                        # 주사위 값 열에 숫자가 있는지 확인
                        if dice_value_col.isdigit():
                            dice_value = int(dice_value_col)
                            
                            # 아이템 이름과 설명이 있는지 확인
                            item_name = ""
                            item_desc = ""
                            
                            if len(row) > start_col_index + 1:
                                item_name = row[start_col_index + 1].strip()
                            
                            if len(row) > start_col_index + 2:
                                item_desc = row[start_col_index + 2].strip()
                            
                            # 아이템 이름이 있는 경우만 저장
                            if item_name:
                                location_mapping[location][dice_value] = {
                                    "name": item_name,
                                    "description": item_desc
                                }
        
        # JSON 파일로 저장
        save_json(dice_items_file, location_mapping)
        
        # 로딩 결과 출력
        for location, mapping in location_mapping.items():
            log_info(f"{location}: {len(mapping)}개 아이템 매핑됨")
        
        log_info("장소별 주사위-아이템 맵핑 데이터를 성공적으로 로드했습니다.")
        return location_mapping
    except Exception as e:
        log_error(f"주사위-아이템 맵핑 데이터 로드 중 오류 발생: {e}", e)
        # 기본 데이터로 초기화
        return {location: {} for location in location_ranges.keys()}

#######################
# 날씨 시스템 관련 함수들
#######################

def get_weather_system(bot):
    """날씨 시스템 인스턴스 반환"""
    weather_cog = bot.get_cog('WeatherCommands')
    if weather_cog and hasattr(weather_cog, 'weather_system'):
        return weather_cog.weather_system
    return None

async def apply_weather_effects_to_dice(bot, minigame_name, dice_roll, channel_id=None, minigame_id=None):
    """
    날씨 효과를 주사위 결과에 적용
    
    Args:
        bot: 디스코드 봇 인스턴스
        minigame_name: 미니게임 이름 (예: "낚시", "채광", "채집" 등)
        dice_roll: 원래 주사위 결과
        channel_id: 미니게임이 실행된 채널 ID (채널별 날씨용)
        minigame_id: 미니게임 고유 ID (게임 시작 시 등록된 경우)
    
    Returns:
        수정된 주사위 결과
    """
    weather_system = get_weather_system(bot)
    if not weather_system:
        return dice_roll
    
    # 미니게임 ID가 주어진 경우 해당 ID의 날씨 효과 적용
    if minigame_id:
        effects = weather_system.get_minigame_weather_effects(minigame_id, minigame_name)
    else:
        # 아니면 현재 날씨 효과 적용
        effects = weather_system.get_current_weather_for_minigame(minigame_name, channel_id)
    
    # 주사위 수정
    dice_mod = effects.get('dice_mod', 0)
    modified_dice = dice_roll + dice_mod
    
    # 최대값 제한 (150)
    modified_dice = min(150, max(1, modified_dice))
    
    # 디버그 로그
    if dice_mod != 0:
        log_debug(f"날씨 효과 적용: {minigame_name} 주사위 {dice_roll} -> {modified_dice} (날씨 수정: {dice_mod:+d})")
    
    return modified_dice

def should_apply_horror_mode(bot, minigame_name, channel_id=None, minigame_id=None):
    """공포모드 적용 여부 확인"""
    weather_system = get_weather_system(bot)
    if not weather_system:
        return False
    
    # 미니게임 ID가 주어진 경우 해당 ID의 날씨 효과 적용
    if minigame_id:
        effects = weather_system.get_minigame_weather_effects(minigame_id, minigame_name)
    else:
        # 아니면 현재 날씨 효과 적용
        effects = weather_system.get_current_weather_for_minigame(minigame_name, channel_id)
    
    horror_mode = effects.get('horror_mode', False)
    
    # 확률 적용
    if horror_mode and weather_system.should_give_horror_item():
        log_info(f"공포모드 적용: {minigame_name}")
        return True
    
    return False

def should_apply_unique_items(bot, minigame_name, channel_id=None, minigame_id=None):
    """유니크 아이템 적용 여부 확인"""
    weather_system = get_weather_system(bot)
    if not weather_system:
        return False
    
    # 미니게임 ID가 주어진 경우 해당 ID의 날씨 효과 적용
    if minigame_id:
        effects = weather_system.get_minigame_weather_effects(minigame_id, minigame_name)
    else:
        # 아니면 현재 날씨 효과 적용
        effects = weather_system.get_current_weather_for_minigame(minigame_name, channel_id)
    
    unique_items = effects.get('unique_items', False)
    
    # 확률 적용
    if unique_items and weather_system.should_give_unique_item():
        log_info(f"유니크 아이템 적용: {minigame_name}")
        return True
    
    return False

def register_minigame_weather(bot, minigame_id, channel_id=None):
    """미니게임 시작 시 날씨 상태 등록"""
    weather_system = get_weather_system(bot)
    if weather_system:
        weather_system.register_minigame(minigame_id, channel_id)
        return True
    return False

def unregister_minigame_weather(bot, minigame_id):
    """미니게임 종료 시 날씨 상태 해제"""
    weather_system = get_weather_system(bot)
    if weather_system:
        weather_system.unregister_minigame(minigame_id)
        return True
    return False

def get_item_for_dice_roll(dice_mapping, dice_roll, bot=None, minigame_name=None, channel_id=None, minigame_id=None):
    """
    주사위 값에 해당하는 아이템 반환 (날씨 효과 적용)
    
    Args:
        dice_mapping: 주사위-아이템 매핑 딕셔너리
        dice_roll: 원래 주사위 결과
        bot: 디스코드 봇 인스턴스
        minigame_name: 미니게임 이름
        channel_id: 미니게임이 실행된 채널 ID
        minigame_id: 미니게임 고유 ID
    
    Returns:
        선택된 아이템, 아이템 종류(일반/공포/유니크)
    """
    item_type = "normal"  # 기본은 일반 아이템
    
    # 날씨 효과가 없으면 일반 아이템 반환
    if not bot or not minigame_name:
        return dice_mapping.get(dice_roll), item_type
    
    # 공포모드 확인
    if should_apply_horror_mode(bot, minigame_name, channel_id, minigame_id):
        item_type = "horror"
        # 공포모드 아이템 매핑 가져오기 (임의의 값 선택)
        horror_keys = sorted([k for k in dice_mapping if 
                              k > 100 and k <= 125])  # U,V,W 열 (101-125)
        if horror_keys:
            horror_key = random.choice(horror_keys)
            return dice_mapping.get(horror_key), item_type
    
    # 유니크 아이템 확인
    if should_apply_unique_items(bot, minigame_name, channel_id, minigame_id):
        item_type = "unique"
        # 유니크 아이템 매핑 가져오기 (임의의 값 선택)
        unique_keys = sorted([k for k in dice_mapping if 
                               k > 75 and k <= 100])  # P,Q,R 열 (76-100)
        if unique_keys:
            unique_key = random.choice(unique_keys)
            return dice_mapping.get(unique_key), item_type
    
    # 일반 아이템 반환
    return dice_mapping.get(dice_roll), item_type

# 모듈 초기화
def init_module():
    """모듈 초기화"""
    # 이미 핸들러가 등록되어 있으면 다시 설정하지 않음
    if not logger.handlers:
        setup_logger()
        log_info("유틸리티 모듈이 초기화되었습니다.")
    else:
        log_debug("유틸리티 모듈이 이미 초기화되어 있습니다.", False)

# 모듈 로드 시 초기화
if __name__ != "__main__":
    init_module()
"""
Call of Duty Military Theme - Mock Battlefield Data Generator

Generates simulated battlefield logs with various event types, threat levels,
and military operation scenarios for the Active Agent demo.
"""

from __future__ import annotations

import random
import time
from datetime import datetime, timedelta
from typing import Any

CALLSIGNS = ["Bravo-6", "Eagle Eye", "Shadow", "Vanguard", "Ghost", "Warhammer", "Phoenix"]
LOCATIONS = [
    "Grid Alpha-7", "Sector Bravo-3", "FOB Delta", "Outpost Echo-9",
    "Highway Foxtrot", "Village Kilo-4", "Ridge Sierra-2", "Bridge Tango-1",
    "Compound Victor", "LZ Whiskey",
]
WEAPONS = [
    "M4A1", "AK-47", "RPG-7", "M249 SAW", "Barrett M82", "MP5",
    "Javelin ATGM", "Stinger MANPAD", "M203 Grenade Launcher", "Claymore Mine",
]
VEHICLES = [
    "BTR-80 APC", "T-72 MBT", "Mi-24 Hind", "UH-60 Black Hawk",
    "HMMWV", "Technical Pickup", "UAV Reaper", "CH-47 Chinook",
]

CRITICAL_EVENTS = [
    {
        "template": "敌方{vehicle}突破{location}防线，我方{callsign}请求火力支援",
        "type": "PERIMETER_BREACH",
    },
    {
        "template": "{callsign}在{location}遭遇伏击，{count}名队员负伤，请求医疗后送",
        "type": "AMBUSH",
    },
    {
        "template": "检测到敌方电子干扰，{location}区域通信中断，影响{callsign}行动",
        "type": "COMMS_DISRUPTED",
    },
    {
        "template": "{location}发现敌方{weapon}阵地，对我方空中资产构成直接威胁",
        "type": "AA_THREAT",
    },
    {
        "template": "紧急：{callsign}在{location}发现大规模敌军集结，预计{count}人编队",
        "type": "ENEMY_MASSING",
    },
]

WARNING_EVENTS = [
    {
        "template": "{callsign}弹药储备降至{pct}%，请求{location}补给投送",
        "type": "LOW_AMMO",
    },
    {
        "template": "侦察报告：{location}附近发现可疑车辆移动，可能为敌方侦察队",
        "type": "RECON_ACTIVITY",
    },
    {
        "template": "天气预警：{location}区域能见度降低，影响{callsign}空中支援",
        "type": "WEATHER_ALERT",
    },
    {
        "template": "{callsign}报告{location}地区平民活动增加，ROE（交战规则）受限",
        "type": "CIVILIAN_PRESENCE",
    },
    {
        "template": "情报警告：截获敌方通信，{location}可能有IED部署",
        "type": "IED_WARNING",
    },
    {
        "template": "{callsign}燃料不足，{location}行动半径受限，请求油料补给",
        "type": "LOW_FUEL",
    },
    {
        "template": "电子侦测：{location}出现未识别无线电信号，{callsign}加强监听",
        "type": "SIGINT_ALERT",
    },
    {
        "template": "{callsign}在{location}发现敌方无人机侦察痕迹，阵地可能暴露",
        "type": "ENEMY_UAV",
    },
]

INFO_EVENTS = [
    {
        "template": "{callsign}完成{location}巡逻任务，区域安全，无异常",
        "type": "PATROL_COMPLETE",
    },
    {
        "template": "补给车队已抵达{location}，{callsign}物资补充完毕",
        "type": "SUPPLY_ARRIVED",
    },
    {
        "template": "{callsign}在{location}完成换岗，当前兵力{count}人",
        "type": "SHIFT_CHANGE",
    },
    {
        "template": "UAV侦察{location}区域扫描完成，未发现敌方活动",
        "type": "UAV_SCAN_CLEAR",
    },
    {
        "template": "{callsign}已到达{location}指定集结点，等待下一步指令",
        "type": "RALLY_POINT",
    },
    {
        "template": "{callsign}完成{location}通信设备例行检测，信号正常",
        "type": "COMMS_CHECK",
    },
    {
        "template": "{location}气象站报告：能见度良好，风速适宜空中作业",
        "type": "WEATHER_NORMAL",
    },
    {
        "template": "{callsign}在{location}完成弹药盘点，储备充足",
        "type": "AMMO_CHECK",
    },
    {
        "template": "医疗队已在{location}完成伤员转运演练，{callsign}确认就绪",
        "type": "MEDICAL_READY",
    },
    {
        "template": "{callsign}完成{location}防御工事加固，掩体状态良好",
        "type": "FORTIFICATION_DONE",
    },
    {
        "template": "卫星链路恢复正常，{location}区域数据传输稳定",
        "type": "SAT_LINK_OK",
    },
    {
        "template": "{callsign}后勤组完成{location}车辆维护，{count}辆载具可用",
        "type": "VEHICLE_MAINT",
    },
]


def _fill_template(event_def: dict) -> dict[str, Any]:
    """Fill an event template with random values."""
    text = event_def["template"].format(
        callsign=random.choice(CALLSIGNS),
        location=random.choice(LOCATIONS),
        vehicle=random.choice(VEHICLES),
        weapon=random.choice(WEAPONS),
        count=random.randint(3, 25),
        pct=random.randint(10, 30),
    )
    return {
        "message": text,
        "event_type": event_def["type"],
    }


def generate_single_event(level: str | None = None) -> dict[str, Any]:
    """Generate a single battlefield event."""
    if level is None:
        roll = random.random()
        if roll < 0.15:
            level = "CRITICAL"
        elif roll < 0.40:
            level = "WARNING"
        else:
            level = "INFO"

    pool = {
        "CRITICAL": CRITICAL_EVENTS,
        "WARNING": WARNING_EVENTS,
        "INFO": INFO_EVENTS,
    }
    event_def = random.choice(pool.get(level, INFO_EVENTS))
    filled = _fill_template(event_def)

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "source": f"TACCOM-{random.randint(1, 9)}",
        "callsign": random.choice(CALLSIGNS),
        "location": random.choice(LOCATIONS),
        "event_type": filled["event_type"],
        "message": filled["message"],
        "metadata": {
            "frequency": f"{random.randint(30, 90)}.{random.randint(100, 999)} MHz",
            "confidence": round(random.uniform(0.7, 1.0), 2),
            "sector_id": f"S-{random.randint(1, 20):02d}",
        },
    }


def generate_batch(
    count: int = 20,
    critical_ratio: float = 0.2,
    warning_ratio: float = 0.25,
) -> list[dict[str, Any]]:
    """Generate a batch of battlefield events with controlled level distribution."""
    events = []
    base_time = datetime.utcnow() - timedelta(seconds=count * 5)

    n_critical = max(1, int(count * critical_ratio))
    n_warning = max(1, int(count * warning_ratio))
    n_info = count - n_critical - n_warning

    levels = (
        ["CRITICAL"] * n_critical
        + ["WARNING"] * n_warning
        + ["INFO"] * n_info
    )
    random.shuffle(levels)

    for i, level in enumerate(levels):
        event = generate_single_event(level)
        ts = base_time + timedelta(seconds=i * random.randint(3, 8))
        event["timestamp"] = ts.isoformat() + "Z"
        event["seq"] = i + 1
        events.append(event)

    return events


def generate_scenario(scenario: str = "ambush") -> list[dict[str, Any]]:
    """Generate a themed scenario with a narrative arc."""
    scenarios = {
        "ambush": _scenario_ambush,
        "air_strike": _scenario_air_strike,
        "recon": _scenario_recon,
        "supply_run": _scenario_supply_run,
    }
    fn = scenarios.get(scenario, _scenario_ambush)
    return fn()


def _scenario_ambush() -> list[dict[str, Any]]:
    loc = random.choice(LOCATIONS)
    cs = random.choice(CALLSIGNS)
    base = datetime.utcnow()
    return [
        _make(base, 0, "INFO", f"{cs}开始在{loc}执行例行巡逻", "PATROL_START"),
        _make(base, 8, "INFO", f"{cs}通信检测正常，与指挥部保持联络", "COMMS_CHECK"),
        _make(base, 12, "INFO", f"UAV确认{loc}路线清晰，{cs}继续推进", "UAV_SCAN_CLEAR"),
        _make(base, 18, "INFO", f"{cs}经过检查站，当地平民活动正常", "CHECKPOINT_PASS"),
        _make(base, 25, "WARNING", f"{cs}报告{loc}发现可疑热源信号", "RECON_ACTIVITY"),
        _make(base, 30, "WARNING", f"情报截获：敌方在{loc}附近有伏击部署迹象", "IED_WARNING"),
        _make(base, 34, "INFO", f"{cs}调整行进队形，进入战斗准备状态", "FORMATION_CHANGE"),
        _make(base, 38, "CRITICAL", f"{cs}在{loc}遭遇伏击！遭受RPG和轻武器交叉火力", "AMBUSH"),
        _make(base, 40, "WARNING", f"{cs}请求附近友军增援，弹药消耗加快", "REINFORCE_REQUEST"),
        _make(base, 42, "CRITICAL", f"{cs}报告2人负伤，请求{loc}紧急医疗后送和火力支援", "CASUALTY"),
        _make(base, 45, "WARNING", f"敌方火力点位于{loc}东侧高地，压制我方移动", "ENEMY_POSITION"),
        _make(base, 48, "INFO", f"Vanguard小组正从南翼迂回包抄敌方阵地", "FLANKING"),
        _make(base, 50, "WARNING", f"空中支援ETA 5分钟，{cs}就地构筑防御阵地", "AIR_SUPPORT_ETA"),
        _make(base, 54, "CRITICAL", f"敌方增援从{loc}北侧接近，预计12人编队携带重武器", "ENEMY_REINFORCE"),
        _make(base, 58, "INFO", f"医疗后送直升机已起飞，预计8分钟抵达", "MEDEVAC_INBOUND"),
        _make(base, 62, "WARNING", f"{cs}弹药储备降至25%，持续消耗中", "LOW_AMMO"),
        _make(base, 65, "INFO", f"Apache到达{loc}上空，敌方火力被压制", "AIR_SUPPORT_ARRIVED"),
        _make(base, 70, "CRITICAL", f"敌方使用{random.choice(WEAPONS)}对我方直升机开火", "AA_THREAT"),
        _make(base, 75, "INFO", f"Apache成功规避并摧毁敌方火力点，空域已安全", "THREAT_NEUTRALIZED"),
        _make(base, 82, "INFO", f"{cs}脱离接触，伤员已后送，返回FOB Delta", "WITHDRAWAL"),
    ]


def _scenario_air_strike() -> list[dict[str, Any]]:
    loc = random.choice(LOCATIONS)
    base = datetime.utcnow()
    return [
        _make(base, 0, "INFO", f"Eagle Eye 完成{loc}区域高空侦察", "UAV_SCAN_CLEAR"),
        _make(base, 6, "INFO", f"Eagle Eye 拍摄{loc}区域高清卫星图像，分析中", "IMAGERY_CAPTURE"),
        _make(base, 10, "WARNING", f"Eagle Eye 在{loc}发现敌方防空阵地部署", "AA_THREAT"),
        _make(base, 15, "INFO", f"情报组确认该型号为SA-8防空系统", "INTEL_CONFIRM"),
        _make(base, 18, "WARNING", f"确认{loc}有2辆SA-8防空导弹车", "AA_THREAT"),
        _make(base, 22, "WARNING", f"{loc}附近检测到搜索雷达扫描信号", "RADAR_DETECT"),
        _make(base, 25, "INFO", f"通知所有空中单位回避{loc}空域", "AIRSPACE_WARNING"),
        _make(base, 28, "CRITICAL", f"敌方防空系统已激活雷达，{loc}空域受威胁", "AA_THREAT"),
        _make(base, 32, "WARNING", f"我方CH-47运输机航线受影响，被迫改道", "ROUTE_CHANGE"),
        _make(base, 35, "INFO", f"请求SEAD（压制敌方防空）任务批准", "MISSION_REQUEST"),
        _make(base, 38, "INFO", f"Warhammer编队完成挂弹，等待起飞指令", "SORTIE_PREP"),
        _make(base, 41, "CRITICAL", f"敌方防空雷达锁定我方Eagle Eye无人机，紧急规避", "RADAR_LOCK"),
        _make(base, 45, "CRITICAL", f"Warhammer 对{loc}防空阵地实施JDAM打击", "AIR_STRIKE"),
        _make(base, 48, "WARNING", f"打击区域烟尘弥漫，BDA评估延迟", "BDA_PENDING"),
        _make(base, 52, "INFO", f"Eagle Eye重新进入{loc}空域执行评估飞行", "REENTRY"),
        _make(base, 55, "INFO", f"BDA（炸弹损伤评估）：{loc}敌方防空阵地已摧毁", "BDA_COMPLETE"),
        _make(base, 58, "CRITICAL", f"发现第二处隐蔽防空阵地在{loc}西侧开火", "AA_THREAT_NEW"),
        _make(base, 62, "WARNING", f"Warhammer编队紧急规避，请求二次打击授权", "SECOND_STRIKE"),
        _make(base, 68, "INFO", f"二次打击完成，残余防空力量已清除", "STRIKE_COMPLETE"),
        _make(base, 72, "INFO", f"{loc}空域已全面清除，恢复正常空中行动", "AIRSPACE_CLEAR"),
    ]


def _scenario_recon() -> list[dict[str, Any]]:
    loc = random.choice(LOCATIONS)
    base = datetime.utcnow()
    return [
        _make(base, 0, "INFO", f"Shadow 小组出发执行{loc}深度侦察任务", "RECON_START"),
        _make(base, 8, "INFO", f"Shadow 通过出发线，进入敌方控制区外围", "PHASE_LINE"),
        _make(base, 15, "INFO", f"Shadow 已渗透至{loc}外围，开始观察", "RECON_OBSERVE"),
        _make(base, 20, "INFO", f"Shadow 设置隐蔽观察点，开始拍照记录", "OBS_POST_SET"),
        _make(base, 25, "INFO", f"UAV为Shadow提供远程态势感知覆盖", "UAV_OVERWATCH"),
        _make(base, 30, "WARNING", f"Shadow 发现{loc}有大量敌军车辆调动", "RECON_ACTIVITY"),
        _make(base, 35, "WARNING", f"敌方车辆调动频率增加，可能在准备进攻行动", "ACTIVITY_INCREASE"),
        _make(base, 40, "WARNING", f"确认{loc}敌方集结约15辆装甲车辆", "ENEMY_MASSING"),
        _make(base, 44, "INFO", f"Shadow 将情报实时回传指挥部，图像分析中", "INTEL_UPLOAD"),
        _make(base, 48, "WARNING", f"敌方派出搜索犬队，向Shadow方向移动", "SEARCH_PARTY"),
        _make(base, 50, "CRITICAL", f"Shadow 暴露！敌方巡逻队正在搜索{loc}区域", "COMPROMISED"),
        _make(base, 53, "WARNING", f"Shadow 启动紧急规避程序，销毁敏感设备", "EVASION"),
        _make(base, 55, "CRITICAL", f"Shadow 请求紧急撤离，敌方追踪部队逼近", "EXTRACTION_REQUEST"),
        _make(base, 58, "CRITICAL", f"Shadow 遭遇交火，1名队员轻伤，仍可行动", "CONTACT"),
        _make(base, 62, "INFO", f"Phoenix 小组作为掩护力量向{loc}方向机动", "COVER_FORCE"),
        _make(base, 65, "WARNING", f"Black Hawk已起飞前往{loc}执行撤离", "EXTRACTION_INBOUND"),
        _make(base, 70, "INFO", f"Phoenix 以火力牵制敌方追踪部队", "SUPPRESSION"),
        _make(base, 75, "CRITICAL", f"撤离区域遭敌方迫击炮覆盖，LZ被迫转移", "LZ_COMPROMISED"),
        _make(base, 80, "INFO", f"备用LZ确认安全，Black Hawk成功着陆", "LZ_SECURE"),
        _make(base, 85, "INFO", f"Shadow 小组已安全撤离，情报资料已回传", "EXTRACTION_COMPLETE"),
    ]


def _scenario_supply_run() -> list[dict[str, Any]]:
    loc = random.choice(LOCATIONS)
    base = datetime.utcnow()
    return [
        _make(base, 0, "INFO", f"补给车队从FOB Delta出发前往{loc}", "SUPPLY_DEPART"),
        _make(base, 8, "INFO", f"车队编队完成，5辆载具开始行进", "CONVOY_FORMED"),
        _make(base, 15, "INFO", f"前导车辆完成路线扫描，暂无异常", "ROUTE_CLEAR"),
        _make(base, 20, "INFO", f"车队通过检查站Alpha，行进正常", "CHECKPOINT_PASS"),
        _make(base, 28, "WARNING", f"侦察无人机发现{loc}方向有可疑人员活动", "SUSPICIOUS_ACTIVITY"),
        _make(base, 35, "WARNING", f"前方{loc}路段发现可疑路障", "IED_WARNING"),
        _make(base, 39, "INFO", f"车队停车，建立环形防御阵地", "DEFENSIVE_HALT"),
        _make(base, 42, "WARNING", f"EOD小组前进排查，车队暂停", "EOD_CHECK"),
        _make(base, 48, "INFO", f"EOD使用机器人进行近距离排查", "EOD_ROBOT"),
        _make(base, 55, "CRITICAL", f"确认路边IED！{loc}路段封锁，车队改道", "IED_CONFIRMED"),
        _make(base, 58, "CRITICAL", f"IED引爆！前导HMMWV受损，2名人员轻伤", "IED_DETONATION"),
        _make(base, 62, "WARNING", f"可能的二次伏击威胁，加强侧翼警戒", "SECONDARY_THREAT"),
        _make(base, 65, "WARNING", f"替代路线经过敌方活动区域，请求护航", "ESCORT_REQUEST"),
        _make(base, 70, "INFO", f"医疗队处理伤员，伤势稳定可继续行动", "MEDICAL_TREATMENT"),
        _make(base, 75, "CRITICAL", f"替代路线遭遇小规模伏击，敌方使用轻武器射击", "AMBUSH_MINOR"),
        _make(base, 78, "WARNING", f"车队反击火力压制敌方，请求空中支援清除威胁", "COUNTER_FIRE"),
        _make(base, 82, "INFO", f"Apache提供空中护航，敌方撤离", "ESCORT_ACTIVE"),
        _make(base, 88, "CRITICAL", f"侦测到敌方RPG小组在{loc}入口处设伏", "RPG_THREAT"),
        _make(base, 92, "INFO", f"Apache消除RPG威胁，车队恢复行进", "THREAT_CLEARED"),
        _make(base, 98, "INFO", f"补给车队安全抵达{loc}，任务完成", "SUPPLY_ARRIVED"),
    ]


def _make(base: datetime, offset_sec: int, level: str, msg: str, etype: str) -> dict[str, Any]:
    ts = base + timedelta(seconds=offset_sec)
    return {
        "timestamp": ts.isoformat() + "Z",
        "level": level,
        "source": f"TACCOM-{random.randint(1, 9)}",
        "callsign": random.choice(CALLSIGNS),
        "location": random.choice(LOCATIONS),
        "event_type": etype,
        "message": msg,
        "seq": offset_sec,
        "metadata": {
            "frequency": f"{random.randint(30, 90)}.{random.randint(100, 999)} MHz",
            "confidence": round(random.uniform(0.7, 1.0), 2),
        },
    }


AVAILABLE_SCENARIOS = ["ambush", "air_strike", "recon", "supply_run"]

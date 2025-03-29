from rasa_sdk import Action
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk import Tracker
from rasa_sdk.types import DomainDict
import requests
import uuid
import os
import yaml
import re
import json
import sqlite3
from collections import defaultdict
from typing import Text, Dict, Any, List

# ========= XMind 解析工具导入 ========= #
from .utils.xmind_parser import extract_paths_from_xmind
from .utils.story_generator import generate_stories_yaml

# ========= 通用 URL 提取 ========= #
def extract_url_by_suffix(text: str, suffix: str) -> str:
    urls = re.findall(r"(https?://[^\s]+)", text)
    for url in urls:
        if url.endswith(suffix):
            return url
    return None

# ========= YAML 修复器：修复多重冒号与换行 ========= #
def fix_yaml_colons_and_multilines(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    fixed_lines = []
    skip_next = False

    for i in range(len(lines)):
        if skip_next:
            skip_next = False
            continue

        line = lines[i].rstrip("\n")

        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if re.match(r'^\s*-\s*(story|action):\s*["\']?.*["\']?\s*$', line.strip()) and next_line.startswith("("):
                prefix = line.strip().split(":", 1)[0]
                content = line.strip().split(":", 1)[1].strip()
                combined = f'{prefix}: "{content} {next_line.strip()}"\n'
                fixed_lines.append(combined)
                skip_next = True
                continue

        match = re.match(r'^(\s*-\s*(story|intent|action): )(.+)$', line)
        if match:
            prefix = match.group(1)
            value = match.group(3).strip()
            if ":" in value and not value.startswith('"'):
                value = f'"{value}"'
            fixed_lines.append(f"{prefix}{value}\n")
        else:
            fixed_lines.append(line + "\n")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)

# ========= XMind Action ========= #
class ActionParseUploadedXmind(Action):
    def name(self):
        return "action_parse_uploaded_xmind"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        url = extract_url_by_suffix(tracker.latest_message.get("text", ""), ".xmind")
        if not url:
            dispatcher.utter_message(text="❌ 未检测到有效的 .xmind 文件链接。")
            return []

        try:
            os.makedirs("files", exist_ok=True)
            local_filename = f"files/{uuid.uuid4().hex}.xmind"
            with open(local_filename, "wb") as f:
                f.write(requests.get(url).content)

            paths = extract_paths_from_xmind(local_filename)
            count = generate_stories_yaml(paths)
            dispatcher.utter_message(text=f"✅ 解析成功，生成 {count} 条对话路径。")

            def normalize(text): return text.replace("_", " ").capitalize()

            def extract_utterances_from_stories(story_file="data/stories_auto.yml"):
                with open(story_file, "r", encoding="utf-8") as f:
                    return sorted(set(re.findall(r"utter_[a-zA-Z0-9_]+", f.read())))

            def generate_responses_yaml(utterances, output_file="data/responses_auto.yml"):
                responses = {"responses": {}}
                for u in utterances:
                    responses["responses"][u] = [{"text": normalize(u)}]
                with open(output_file, "w", encoding="utf-8") as f:
                    yaml.dump(responses, f, allow_unicode=True)
                return output_file, len(utterances)

            fix_yaml_colons_and_multilines("data/stories_auto.yml")

            utterances = extract_utterances_from_stories()
            output_file, count = generate_responses_yaml(utterances)
            dispatcher.utter_message(text=f"✅ 已生成 {count} 个响应，写入 {output_file}。")

            def extract_intents_actions(story_file="data/stories_auto.yml"):
                with open(story_file, "r", encoding="utf-8") as f:
                    content = f.read()
                intents = sorted(set(re.findall(r"intent: ([a-zA-Z0-9_]+)", content)))
                actions = sorted(set(re.findall(r"action: ([a-zA-Z0-9_]+)", content)))
                return intents, actions

            def update_domain(domain_file="domain.yml", intents=None, actions=None):
                with open(domain_file, "r", encoding="utf-8") as f:
                    d = yaml.safe_load(f)
                d["intents"] = sorted(set(d.get("intents", []) + intents))
                d["actions"] = sorted(set(d.get("actions", []) + actions))
                with open(domain_file, "w", encoding="utf-8") as f:
                    yaml.dump(d, f, allow_unicode=True)

            intents, actions = extract_intents_actions()
            update_domain(intents=intents, actions=actions)
            dispatcher.utter_message(text=f"✅ 更新 domain.yml：{len(intents)} intents, {len(actions)} actions。")

            def build_tree(stories):
                tree = lambda: defaultdict(tree)
                root = tree()
                for s in stories:
                    steps = s.get("steps", [])
                    current = root
                    for step in steps:
                        k = ""
                        if "intent" in step:
                            k = f"intent::{step['intent']}"
                        elif "action" in step:
                            k = f"action::{step['action']}"
                        if k:
                            current = current[k]
                return root

            def tree_to_dict(d):
                return {k: tree_to_dict(v) for k, v in d.items()} if isinstance(d, defaultdict) else d

            def generate_json(story_file="data/stories_auto.yml", output_file="data/TreeMap.json"):
                with open(story_file, "r", encoding="utf-8") as f:
                    stories = yaml.safe_load(f)
                tree = build_tree(stories)
                json_tree = tree_to_dict(tree)
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(json_tree, f, ensure_ascii=False, indent=2)
                return output_file

            json_path = generate_json()
            dispatcher.utter_message(text=f"📁 已生成 TreeMap 结构：{json_path}")

        except Exception as e:
            dispatcher.utter_message(text=f"❌ XMind 处理失败：{e}")
        finally:
            if os.path.exists(local_filename):
                os.remove(local_filename)

        return []


# ========= WTO Case Action ========= #
BASE_DB_PATH = "./data/WTO/WTOCaseBase.db"
TEMP_TXT_PATH = "./data/WTO/CaseTemp/"
TEMP_DB_PATH = "./data/WTO/CaseTemp/NewCaseTemp.db"

SECTION_HEADERS = [
    "Case Number and Name", "Current status", "Key facts", "Latest document",
    "Summary of the dispute to date", "Consultations",
    "Panel and Appellate Body proceedings", "Implementation of adopted reports"
]

def extract_sections(text, headers):
    pattern = rf"({'|'.join(re.escape(h) for h in headers)})\n(.*?)(?=\n({'|'.join(re.escape(h) for h in headers)})\n|\Z)"
    return {h: c.strip() for h, c, _ in re.findall(pattern, text, re.DOTALL)}

def extract_field(text, key):
    m = re.search(rf"{key}:\s*(.+)", text)
    return m.group(1).strip() if m else ""

def extract_agreements(text):
    matches = re.findall(r"Agreements cited:\n\(as cited in .*?\)\s*(.+?)(?=\n[A-Z]|$)", text, re.DOTALL)
    return " | ".join(m.strip() for m in matches) if matches else ""

def map_to_treemap(case_id, data):
    kf = data.get("Key facts", "")
    return {
        "case_id": case_id,
        "number_and_name": data.get("Case Number and Name", ""),
        "current_status": data.get("Current status", ""),
        "short_title": extract_field(kf, "Short title"),
        "complainant": extract_field(kf, "Complainant"),
        "respondent": extract_field(kf, "Respondent"),
        "third_parties": extract_field(kf, "Third Parties"),
        "agreements_cited": extract_agreements(kf),
        "consultations_requested": extract_field(kf, "Consultations requested"),
        "panel_requested": extract_field(kf, "Panel requested"),
        "panel_established": extract_field(kf, "Panel established"),
        "panel_composed": extract_field(kf, "Panel composed"),
        "panel_report_circulated": extract_field(kf, "Panel report circulated"),
        "appellate_body_report_circulated": extract_field(kf, "Appellate Body report circulated"),
        "summary": data.get("Summary of the dispute to date", ""),
        "consultations": data.get("Consultations", ""),
        "panel_and_appellate": data.get("Panel and Appellate Body proceedings", ""),
        "implementation": data.get("Implementation of adopted reports", ""),
        "latest_document": data.get("Latest document", "")
    }

class ActionUploadWTOCase(Action):
    def name(self):
        return "action_upload_wto_case"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        url = extract_url_by_suffix(tracker.latest_message.get("text", ""), ".txt")
        if not url:
            dispatcher.utter_message(text="❌ 未识别到 .txt WTO 案件链接。")
            return []

        try:
            os.makedirs(TEMP_TXT_PATH, exist_ok=True)
            text = requests.get(url).text
            filename = os.path.basename(url)
            temp_path = os.path.join(TEMP_TXT_PATH, filename)
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            dispatcher.utter_message(text=f"❌ 下载失败: {e}")
            return []

        data = extract_sections(text, SECTION_HEADERS)
        case_id_match = re.search(r"(DS\\d+)", data.get("Case Number and Name", "") or text)
        if not case_id_match:
            dispatcher.utter_message(text="❌ 未识别案件编号（如 DS309）")
            return []
        case_id = case_id_match.group(1)
        case_data = map_to_treemap(case_id, data)

        os.makedirs(os.path.dirname(TEMP_DB_PATH), exist_ok=True)
        conn_main = sqlite3.connect(BASE_DB_PATH)
        cur = conn_main.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS wto_cases (
                case_id TEXT PRIMARY KEY,
                number_and_name TEXT,
                current_status TEXT,
                short_title TEXT,
                complainant TEXT,
                respondent TEXT,
                third_parties TEXT,
                agreements_cited TEXT,
                consultations_requested TEXT,
                panel_requested TEXT,
                panel_established TEXT,
                panel_composed TEXT,
                panel_report_circulated TEXT,
                appellate_body_report_circulated TEXT,
                summary TEXT,
                consultations TEXT,
                panel_and_appellate TEXT,
                implementation TEXT,
                latest_document TEXT
            )""")

        cur.execute("SELECT 1 FROM wto_cases WHERE case_id = ?", (case_id,))
        if cur.fetchone():
            dispatcher.utter_message(text=f"WTO 案件已存在：{case_id}")
        else:
            cur.execute("""
                INSERT INTO wto_cases VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, tuple(case_data.values()))
            conn_main.commit()
            dispatcher.utter_message(text=f"✅ 成功添加 WTO 案件：{case_id}")

        conn_main.close()
        return []

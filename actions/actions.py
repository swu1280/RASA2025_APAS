from rasa_sdk import Action
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk import Tracker
from rasa_sdk.events import SlotSet
import requests
import uuid
import os
import subprocess

import yaml
import re

from .utils.xmind_parser import extract_paths_from_xmind
from .utils.story_generator import generate_stories_yaml

import json
from collections import defaultdict

from typing import Text, Dict, Any, List
from rasa_sdk.types import DomainDict

class ActionParseUploadedXmind(Action):
    def name(self):
        return "action_parse_uploaded_xmind"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        # Step 1: 获取用户输入中可能存在的 URL
        user_msg = tracker.latest_message.get("text", "")
        url = self.extract_url(user_msg)

        if not url:
            dispatcher.utter_message(text="❌ 未检测到有效的 .xmind 文件链接，请提供有效的 URL。")
            return []

        # Step 2: 下载文件
        try:
            os.makedirs("files", exist_ok=True)
            local_filename = f"files/{uuid.uuid4().hex}.xmind"
            response = requests.get(url)
            response.raise_for_status()
            with open(local_filename, "wb") as f:
                f.write(response.content)
        except Exception as e:
            dispatcher.utter_message(text=f"❌ 下载文件失败：{e}")
            return []

        # Step 3: 解析 xmind 内容，生成 stories
        try:
            paths = extract_paths_from_xmind(local_filename)
            count = generate_stories_yaml(paths)
            dispatcher.utter_message(text=f"✅ 成功解析文件，生成 {count} 条对话路径，已写入 stories_auto.yml。")
            
            

            def normalize(text):
                return text.replace("_", " ").capitalize()

            def extract_utterances_from_stories(story_file="data/stories_auto.yml"):
                with open(story_file, "r", encoding="utf-8") as f:
                    content = f.read()

                return sorted(set(re.findall(r"utter_[a-zA-Z0-9_]+", content)))

            def generate_responses_yaml(utterances, output_file="data/responses_auto.yml"):
                responses = {"responses": {}}
                for utter in utterances:
                    responses["responses"][utter] = [{"text": normalize(utter)}]

                with open(output_file, "w", encoding="utf-8") as f:
                    yaml.dump(responses, f, allow_unicode=True)

                return output_file, len(utterances)

            
            # 修复 stories_auto.yml 中因冒号导致的 YAML 错误
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

                    # 检查是否是非法换行的 story 或 action
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if re.match(r'^\s*-\s*(story|action):\s*["\']?.*["\']?\s*$', line.strip()) and next_line.startswith("("):
                            # 合并当前行和下一行
                            prefix = line.strip().split(":", 1)[0]  # - story or - action
                            combined = f'{prefix}: "{line.strip().split(":", 1)[1].strip()} {next_line.strip()}"\n'
                            fixed_lines.append(combined)
                            skip_next = True
                            continue

                    # 检查是否含有多重冒号
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


            fix_yaml_colons_and_multilines("data/stories_auto.yml")

            
            
            utterances = extract_utterances_from_stories()
            output_file, count = generate_responses_yaml(utterances)
            dispatcher.utter_message(text=f"✅ 已生成 {count} 个响应，写入 {output_file}。")




            def extract_intents_and_actions(story_file="data/stories_auto.yml"):
                with open(story_file, "r", encoding="utf-8") as f:
                    content = f.read()

                intents = sorted(set(re.findall(r"intent: ([a-zA-Z0-9_]+)", content)))
                actions = sorted(set(re.findall(r"action: ([a-zA-Z0-9_]+)", content)))
                return intents, actions

            def update_domain(domain_file="domain.yml", intents=None, actions=None):
                with open(domain_file, "r", encoding="utf-8") as f:
                    domain = yaml.safe_load(f)

                domain["intents"] = sorted(set(domain.get("intents", []) + intents))
                domain["actions"] = sorted(set(domain.get("actions", []) + actions))

                with open(domain_file, "w", encoding="utf-8") as f:
                    yaml.dump(domain, f, allow_unicode=True)

            intents, actions = extract_intents_and_actions()
            update_domain(intents=intents, actions=actions)
            #print(f"✅ 已更新 domain.yml：新增 intents {len(intents)} 项，actions {len(actions)} 项。")
            dispatcher.utter_message(text=f"✅ 已更新 domain.yml：新增 intents {len(intents)} 项，actions {len(actions)} 项。")

            
            #### 生成json树

            def build_topic_tree(stories):
                tree = lambda: defaultdict(tree)
                root = tree()
                for story in stories:
                    steps = story.get("steps", [])
                    current_level = root
                    for step in steps:
                        key = ""
                        if "intent" in step:
                            key = f"intent::{step['intent']}"
                        elif "action" in step:
                            key = f"action::{step['action']}"
                        if key:
                            current_level = current_level[key]
                return root

            def defaultdict_to_dict(d):
                if isinstance(d, defaultdict):
                    return {k: defaultdict_to_dict(v) for k, v in d.items()}
                return d

            def generate_json_tree_from_stories(story_file="data/stories_auto.yml", output_file="data/TreeMap.json"):
                with open(story_file, "r", encoding="utf-8") as f:
                    stories = yaml.safe_load(f)
                tree = build_topic_tree(stories)
                json_tree = defaultdict_to_dict(tree)
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(json_tree, f, ensure_ascii=False, indent=2)
                return output_file

            # 在流程中调用它
            json_path = generate_json_tree_from_stories()
            dispatcher.utter_message(text=f"📁 已生成 JSON 结构树，保存为 {json_path}。")


            subprocess.run(["rasa", "train"], check=True)
            dispatcher.utter_message(text="🧠 模型训练已启动，完成后可开始对话。")
        



        except Exception as e:
            dispatcher.utter_message(text=f"❌ 解析 .xmind 文件失败：{e}")
        finally:
            os.remove(local_filename)  # 删除临时文件

        return []

    def extract_url(self, text):
        import re
        urls = re.findall(r"(https?://[^\s]+)", text)
        for url in urls:
            if url.endswith(".xmind"):
                return url
        return None

# =================== WTO TXT Upload Action ======================

import os
import re
import json
import sqlite3
import requests

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
    matches = re.findall(pattern, text, re.DOTALL)
    return {header: content.strip() for header, content, _ in matches}

def extract_field(text, key):
    match = re.search(rf"{key}:\s*(.+)", text)
    return match.group(1).strip() if match else ""

def extract_agreements(text):
    matches = re.findall(r"Agreements cited:\n\(as cited in .*?\)\s*(.+?)(?=\n[A-Z]|$)", text, re.DOTALL)
    return " | ".join(m.strip() for m in matches) if matches else ""

def map_to_treemap_format(case_id, data):
    key_facts = data.get("Key facts", "")
    return {
        "case_id": case_id,
        "number_and_name": data.get("Case Number and Name", ""),
        "current_status": data.get("Current status", ""),
        "short_title": extract_field(key_facts, "Short title"),
        "complainant": extract_field(key_facts, "Complainant"),
        "respondent": extract_field(key_facts, "Respondent"),
        "third_parties": extract_field(key_facts, "Third Parties"),
        "agreements_cited": extract_agreements(key_facts),
        "consultations_requested": extract_field(key_facts, "Consultations requested"),
        "panel_requested": extract_field(key_facts, "Panel requested"),
        "panel_established": extract_field(key_facts, "Panel established"),
        "panel_composed": extract_field(key_facts, "Panel composed"),
        "panel_report_circulated": extract_field(key_facts, "Panel report circulated"),
        "appellate_body_report_circulated": extract_field(key_facts, "Appellate Body report circulated"),
        "summary": data.get("Summary of the dispute to date", ""),
        "consultations": data.get("Consultations", ""),
        "panel_and_appellate": data.get("Panel and Appellate Body proceedings", ""),
        "implementation": data.get("Implementation of adopted reports", ""),
        "latest_document": data.get("Latest document", "")
    }

class ActionUploadWTOCase(Action):
    def name(self) -> Text:
        return "action_upload_wto_case"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: DomainDict) -> List[Dict[Text, Any]]:

        case_url = tracker.get_slot("case_url")
        if not case_url:
            dispatcher.utter_message(text="请提供 WTO 案件文件的链接（TXT 格式）。")
            return []

        try:
            os.makedirs(TEMP_TXT_PATH, exist_ok=True)
            response = requests.get(case_url)
            response.encoding = 'utf-8'
            text = response.text
            filename = os.path.basename(case_url)
            temp_txt_path = os.path.join(TEMP_TXT_PATH, filename)
            with open(temp_txt_path, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            dispatcher.utter_message(text=f"无法下载文件: {e}")
            return []

        data = extract_sections(text, SECTION_HEADERS)
        case_id_match = re.search(r"(DS\d+)", data.get("Case Number and Name", ""))
        if not case_id_match:
            dispatcher.utter_message(text="未识别到 WTO 案件编号（例如 DS252）。")
            return []
        case_id = case_id_match.group(1)

        case_data = map_to_treemap_format(case_id, data)
        os.makedirs(os.path.dirname(TEMP_DB_PATH), exist_ok=True)
        conn_temp = sqlite3.connect(TEMP_DB_PATH)
        cursor_temp = conn_temp.cursor()
        cursor_temp.execute("DROP TABLE IF EXISTS wto_cases")
        cursor_temp.execute("""
            CREATE TABLE wto_cases (
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
            )
        """)
        cursor_temp.execute("""
            INSERT OR REPLACE INTO wto_cases VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, tuple(case_data.values()))
        conn_temp.commit()
        conn_temp.close()

        conn_main = sqlite3.connect(BASE_DB_PATH)
        cursor_main = conn_main.cursor()
        cursor_main.execute("""
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
            )
        """)

        cursor_main.execute("SELECT 1 FROM wto_cases WHERE case_id = ?", (case_id,))
        if cursor_main.fetchone():
            dispatcher.utter_message(text=f"WTO case 数据已存在：{case_id}")
            conn_main.close()
        else:
            cursor_main.execute("""
                INSERT INTO wto_cases VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, tuple(case_data.values()))
            conn_main.commit()
            conn_main.close()
            dispatcher.utter_message(text=f"✅ 成功添加 WTO 案件：{case_id}")

        try:
            for f in os.listdir(TEMP_TXT_PATH):
                os.remove(os.path.join(TEMP_TXT_PATH, f))
        except Exception as cleanup_error:
            dispatcher.utter_message(text=f"⚠️ 数据添加成功，但临时文件清理失败：{cleanup_error}")

        return []
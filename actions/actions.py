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

from dotenv import load_dotenv
load_dotenv()


from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.schema import Document
from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOpenAI

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
FAISS_PATH = "./data/WTO/WTO_FAISS_INDEX"

SECTION_HEADERS = [
    "Case Number and Name", "Current status", "Key facts", "Latest document",
    "Summary of the dispute to date", "Consultations",
    "Panel and Appellate Body proceedings", "Implementation of adopted reports"
]

def extract_sections(text: str, headers: List[str]) -> Dict[str, str]:
    # 构造标题正则
    pattern = "(" + "|".join(re.escape(h) for h in headers) + ")"
    splits = re.split(pattern, text)

    sections = {}
    current = None
    for part in splits:
        part = part.strip()
        if part in headers:
            current = part
            sections[current] = ""
        elif current:
            sections[current] += part + " "

    # 清理多余换行和前后空白
    for k in sections:
        clean = sections[k]
        clean = re.sub(r"\n+", "\n", clean)            # 多个换行合并
        clean = clean.strip("\n ")                     # 移除开头和结尾换行/空格
        sections[k] = clean

    return sections


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
        print(json.dumps(data, indent=2, ensure_ascii=False))
        case_id_match = re.search(r"(DS\d+)", data.get("Case Number and Name", "") or text)
        if not case_id_match:
            dispatcher.utter_message(text="❌ 未识别案件编号")
            return []
        case_id = case_id_match.group(1)
        case_data = map_to_treemap(case_id, data)
        print("🧪 case_data = ", json.dumps(case_data, indent=2, ensure_ascii=False))


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

        self.build_wto_vector_store(case_id, case_data, dispatcher)
        return []

    def safe_generate_documents(self, case_data):
        documents = []
        skipped = []
        for k, v in case_data.items():
            if k != "case_id" and v and isinstance(v, str) and len(v.strip()) > 3:
                documents.append(Document(page_content=v.strip(), metadata={"case_id": case_data['case_id'], "field": k}))
            else:
                skipped.append(k)
        return documents, skipped

    def build_wto_vector_store(self, case_id: str, case_data: dict, dispatcher: CollectingDispatcher) -> None:
        try:
            print("🏁 正在构建向量...")
            embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
            documents, skipped = self.safe_generate_documents(case_data)

            print(f"📄 共生成 {len(documents)} 条文档，跳过字段：{skipped}")

            if not documents:
                dispatcher.utter_message(text=f"⚠️ WTO 案件 {case_id} 向量化失败：无有效内容。跳过字段：{skipped}")
                return

            index_path = "./data/WTO/WTO_FAISS_INDEX"
            print(f"📂 保存路径：{index_path}")

            if os.path.exists(index_path):
                print("📦 已有向量库，追加内容")
                vector_store = FAISS.load_local(index_path, embedding_model)
                vector_store.add_documents(documents)
            else:
                print("📦 向量库不存在，首次创建")
                vector_store = FAISS.from_documents(documents, embedding_model)

            vector_store.save_local(index_path)
            print("✅ 保存完成，当前目录内容：", os.listdir(index_path))
            dispatcher.utter_message(text=f"✅ 向量构建完成：{len(documents)} 个文档，跳过：{skipped}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            dispatcher.utter_message(text=f"❌ 向量构建失败：{e}")

# ========= WTO 问答 Action ========= #
class ActionAskWTOKnowledge(Action):
    def name(self) -> Text:
        return "action_ask_wto_knowledge"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: DomainDict) -> List[Dict[Text, Any]]:

        query = tracker.latest_message.get("text", "")
        try:
            embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
            db = FAISS.load_local("./data/WTO/WTO_FAISS_INDEX", embedding_model)
            retriever = db.as_retriever(search_kwargs={"k": 10})
            llm = ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo")
            qa = RetrievalQA.from_chain_type(llm=llm, retriever=retriever)


            docs = retriever.get_relevant_documents(query)
            print("\n=== 召回内容 ===")
            for d in docs:
                print(f"[{d.metadata.get('case_id')}][{d.metadata.get('field')}] {d.page_content[:100]}...\n")

            result = qa.run(query)
            dispatcher.utter_message(text=f"📖 回答：{result}")
        except Exception as e:
            dispatcher.utter_message(text=f"⚠️ 查询失败：{e}")

       

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


import yaml
import re

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

    print(f"✅ 已更新 domain.yml：新增 intents {len(intents)} 项，actions {len(actions)} 项。")

if __name__ == "__main__":
    intents, actions = extract_intents_and_actions()
    update_domain(intents=intents, actions=actions)

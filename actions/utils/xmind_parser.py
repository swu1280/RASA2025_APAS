import zipfile, json

def extract_paths_from_xmind(xmind_path):
    with zipfile.ZipFile(xmind_path, 'r') as zip_ref:
        content_json = zip_ref.read('content.json')
        content_data = json.loads(content_json)[0]
        return traverse(content_data['rootTopic'])

def traverse(topic, path=None):
    if path is None:
        path = []
    current_title = topic.get("title", "Unknown")
    current_path = path + [current_title]
    paths = []
    children = topic.get("children", {}).get("attached", [])
    if not children:
        return [current_path]
    for child in children:
        paths.extend(traverse(child, current_path))
    return paths

"""创建树形任务测试数据，验证看板渲染"""
import json
import urllib.request

BASE = "http://localhost:9080/api"

def post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def get(path):
    with urllib.request.urlopen(f"{BASE}{path}") as resp:
        return json.loads(resp.read())

# 创建带 children 的树形任务
result = post("/tasks", {
    "feature_id": "test/tree-render",
    "tasks": [
        {
            "title": "节点A：数据库改造",
            "children": [
                {"title": "添加 parent_id 字段"},
                {"title": "添加 task_type 字段"},
                {"title": "迁移脚本编写"},
            ]
        },
        {
            "title": "节点B：接口改造",
            "children": [
                {"title": "batch_create 支持 children"},
                {"title": "list_by_feature 返回树形"},
            ]
        },
        {"title": "普通任务：更新文档"},
    ]
})
print("创建结果:", result)

# 查询验证
data = get("/tasks?feature_id=test/tree-render")
print(f"\n查询到 {len(data['tasks'])} 个顶级任务:")
for t in data["tasks"]:
    kids = t.get("children", [])
    if kids:
        print(f"  [节点] {t['title']} (status={t['status']}, children={len(kids)})")
        for c in kids:
            print(f"    - {c['title']} (status={c['status']})")
    else:
        print(f"  [任务] {t['title']} (status={t['status']})")

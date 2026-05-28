"""
生产环境测试脚本

用于在内网环境下测试Halo同步服务是否正常运行。
测试流程：
1. 健康检查
2. 手动创建投稿
3. 查看投稿列表
4. 测试 Halo 连接
5. 同步到 Halo

使用方法：
    python test_production.py
"""

import requests
import json
import sys

BASE_URL = "http://localhost:5000"


def print_step(step: int, title: str):
    print(f"\n{'='*60}")
    print(f"步骤 {step}: {title}")
    print('='*60)


def print_result(response: requests.Response):
    print(f"状态码: {response.status_code}")
    try:
        data = response.json()
        print(f"响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
        return data
    except:
        print(f"响应: {response.text}")
        return None


def test_health():
    print_step(1, "健康检查")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        data = print_result(response)
        return response.status_code == 200
    except Exception as e:
        print(f"错误: {e}")
        return False


def test_create_post():
    print_step(2, "手动创建测试投稿")
    post_data = {
        "title": "测试投稿-生产环境验证",
        "content": "这是一条测试投稿内容，用于验证生产环境是否正常运行。如果你看到这条投稿，说明服务已经成功部署！",
        "class_name": "测试班级",
        "user_name": "测试用户",
        "wx_nickname": "测试昵称"
    }
    try:
        response = requests.post(
            f"{BASE_URL}/api/posts/create",
            json=post_data,
            timeout=10
        )
        data = print_result(response)
        if data and data.get("status") == "success":
            return data.get("post", {}).get("id")
        return None
    except Exception as e:
        print(f"错误: {e}")
        return None


def test_list_posts():
    print_step(3, "查看投稿列表")
    try:
        response = requests.get(f"{BASE_URL}/api/posts?size=5", timeout=10)
        data = print_result(response)
        return response.status_code == 200
    except Exception as e:
        print(f"错误: {e}")
        return False


def test_halo_connection():
    print_step(4, "测试 Halo 连接")
    try:
        response = requests.get(f"{BASE_URL}/test/halo", timeout=10)
        data = print_result(response)
        if data and data.get("status") == "connected":
            print("\n✅ Halo 连接成功！")
            return True
        else:
            print("\n⚠️ Halo 连接失败，请检查配置")
            return False
    except Exception as e:
        print(f"错误: {e}")
        return False


def test_sync_to_halo(post_id: int = None):
    print_step(5, "同步投稿到 Halo")
    sync_data = {}
    if post_id:
        sync_data["post_ids"] = [post_id]
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/posts/sync-to-halo",
            json=sync_data,
            timeout=30
        )
        data = print_result(response)
        if data and data.get("status") == "completed":
            print(f"\n✅ 成功同步 {data.get('synced_count', 0)} 条投稿到 Halo")
            return True
        return False
    except Exception as e:
        print(f"错误: {e}")
        return False


def test_tduck_connection():
    print_step(6, "测试 tduck 连接（可选）")
    try:
        response = requests.get(f"{BASE_URL}/test/tduck", timeout=10)
        data = print_result(response)
        if data and data.get("status") == "ok":
            print("\n✅ tduck 连接成功！")
            return True
        else:
            print("\n⚠️ tduck 连接失败，请检查配置")
            return False
    except Exception as e:
        print(f"错误: {e}")
        return False


def main():
    print("\n" + "="*60)
    print("   校园墙同步服务 - 生产环境测试")
    print("="*60)
    
    results = []
    
    results.append(("健康检查", test_health()))
    
    post_id = test_create_post()
    results.append(("创建投稿", post_id is not None))
    
    results.append(("查看列表", test_list_posts()))
    
    halo_ok = test_halo_connection()
    results.append(("Halo连接", halo_ok))
    
    if halo_ok:
        results.append(("Halo同步", test_sync_to_halo(post_id)))
    else:
        results.append(("Halo同步", False))
        print("\n⚠️ 跳过 Halo 同步测试（连接失败）")
    
    print("\n" + "="*60)
    print("   测试结果汇总")
    print("="*60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    print("="*60)
    
    if all_passed:
        print("\n🎉 所有测试通过！服务已准备好投入生产。")
        return 0
    else:
        print("\n⚠️ 部分测试失败，请检查配置和日志。")
        return 1


if __name__ == "__main__":
    sys.exit(main())

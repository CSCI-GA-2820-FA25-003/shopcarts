#!/usr/bin/env python3
"""
Database Model Demo Script for Sprint Review
展示database model的核心功能和设计亮点
"""

import requests
import json
import time

# API基础URL
BASE_URL = "http://127.0.0.1:8080"

def demo_database_models():
    """演示database model的核心功能"""
    
    print("🎯 Database Model Demo - Sprint Review")
    print("=" * 50)
    
    # 1. 测试服务状态
    print("\n1. 检查服务状态...")
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print("✅ 服务运行正常")
            print(f"   服务信息: {response.json()}")
        else:
            print("❌ 服务未响应")
            return
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return
    
    # 2. 创建购物车 - 展示Shopcart模型
    print("\n2. 创建购物车 (Shopcart Model)...")
    shopcart_data = {
        "customer_id": 12345,
        "status": "active",
        "total_items": 0
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/shopcarts",
            json=shopcart_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 201:
            shopcart = response.json()
            print("✅ 购物车创建成功")
            print(f"   购物车ID: {shopcart['id']}")
            print(f"   客户ID: {shopcart['customer_id']}")
            print(f"   状态: {shopcart['status']}")
            print(f"   创建时间: {shopcart['created_date']}")
        else:
            print(f"❌ 创建失败: {response.status_code} - {response.text}")
            return
            
    except Exception as e:
        print(f"❌ 创建购物车失败: {e}")
        return
    
    # 3. 添加商品 - 展示ShopcartItem模型
    print("\n3. 添加商品到购物车 (ShopcartItem Model)...")
    
    items_to_add = [
        {
            "product_id": 1001,
            "quantity": 2,
            "price": 19.99,
            "description": "NYU T-Shirt"
        },
        {
            "product_id": 1002,
            "quantity": 1,
            "price": 49.99,
            "description": "NYU Hoodie"
        },
        {
            "product_id": 1003,
            "quantity": 3,
            "price": 9.99,
            "description": "NYU Mug"
        }
    ]
    
    for i, item in enumerate(items_to_add, 1):
        try:
            response = requests.post(
                f"{BASE_URL}/shopcarts/12345/items",
                json=item,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 201:
                created_item = response.json()
                print(f"✅ 商品 {i} 添加成功")
                print(f"   商品ID: {created_item['id']}")
                print(f"   产品ID: {created_item['product_id']}")
                print(f"   数量: {created_item['quantity']}")
                print(f"   价格: ${created_item['price']}")
                print(f"   描述: {created_item['description']}")
            else:
                print(f"❌ 添加商品 {i} 失败: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ 添加商品 {i} 失败: {e}")
    
    # 4. 查看完整购物车 - 展示关系映射
    print("\n4. 查看完整购物车 (Relationship Mapping)...")
    try:
        response = requests.get(
            f"{BASE_URL}/shopcarts/12345",
            headers={"X-Customer-ID": "12345"}
        )
        
        if response.status_code == 200:
            shopcart = response.json()
            print("✅ 购物车详情获取成功")
            print(f"   购物车ID: {shopcart['id']}")
            print(f"   客户ID: {shopcart['customer_id']}")
            print(f"   状态: {shopcart['status']}")
            print(f"   总商品数: {shopcart['total_items']}")
            print(f"   最后修改: {shopcart['last_modified']}")
            print(f"   商品列表:")
            
            for item in shopcart['items']:
                print(f"     - {item['description']} (ID: {item['product_id']})")
                print(f"       数量: {item['quantity']}, 价格: ${item['price']}")
        else:
            print(f"❌ 获取购物车失败: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ 获取购物车失败: {e}")
    
    # 5. 更新商品数量 - 展示upsert功能
    print("\n5. 更新商品数量 (Upsert Functionality)...")
    try:
        update_data = {
            "quantity": 5,
            "price": 19.99,
            "description": "NYU T-Shirt (Updated)"
        }
        
        response = requests.patch(
            f"{BASE_URL}/shopcarts/12345/items/1001",
            json=update_data,
            headers={"X-Customer-ID": "12345"}
        )
        
        if response.status_code == 200:
            updated_item = response.json()
            print("✅ 商品更新成功")
            print(f"   新数量: {updated_item['quantity']}")
            print(f"   新描述: {updated_item['description']}")
        else:
            print(f"❌ 更新商品失败: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ 更新商品失败: {e}")
    
    # 6. 删除商品 - 展示删除功能
    print("\n6. 删除商品 (Delete Functionality)...")
    try:
        response = requests.delete(f"{BASE_URL}/shopcarts/12345/items/1003")
        
        if response.status_code == 204:
            print("✅ 商品删除成功")
        else:
            print(f"❌ 删除商品失败: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ 删除商品失败: {e}")
    
    # 7. 最终购物车状态
    print("\n7. 最终购物车状态...")
    try:
        response = requests.get(
            f"{BASE_URL}/shopcarts/12345",
            headers={"X-Customer-ID": "12345"}
        )
        
        if response.status_code == 200:
            shopcart = response.json()
            print("✅ 最终状态:")
            print(f"   总商品数: {shopcart['total_items']}")
            print(f"   商品数量: {len(shopcart['items'])}")
            for item in shopcart['items']:
                print(f"     - {item['description']}: {item['quantity']} x ${item['price']}")
        else:
            print(f"❌ 获取最终状态失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 获取最终状态失败: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Database Model Demo 完成!")
    print("\n技术亮点总结:")
    print("✅ Shopcart模型 - 购物车管理")
    print("✅ ShopcartItem模型 - 商品管理") 
    print("✅ 关系映射 - One-to-Many关系")
    print("✅ 数据验证 - 完整的错误处理")
    print("✅ 序列化/反序列化 - JSON转换")
    print("✅ CRUD操作 - 创建、读取、更新、删除")
    print("✅ 业务逻辑 - 智能的upsert功能")

if __name__ == "__main__":
    demo_database_models()


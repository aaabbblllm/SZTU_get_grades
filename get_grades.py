"""
自动查询教务系统成绩 - 终极搜寻点击版
"""

import os
import time
import re
import json
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
# 引入这个新模块
from email.utils import formataddr

# ================= 配置区 =================
USERNAME = os.environ.get("STU_ID")
PASSWORD = os.environ.get("STU_PWD")
MAIL_HOST = "smtp.qq.com" 
MAIL_USER = os.environ.get("MAIL_USER")
MAIL_PASS = os.environ.get("MAIL_PASS")
MAIL_RECEIVER = os.environ.get("MAIL_RECEIVER")
# ==========================================



def send_email(title, html_content):
    if not MAIL_USER or not MAIL_PASS: return
    try:
        message = MIMEText(html_content, 'html', 'utf-8')
        # 关键修改：必须要带上发件人邮箱地址
        message['From'] = formataddr(["GPA监控助手", MAIL_USER])
        message['To'] = formataddr(["同学", MAIL_RECEIVER])
        message['Subject'] = Header(title, 'utf-8')

        smtpObj = smtplib.SMTP_SSL(MAIL_HOST, 465)
        smtpObj.login(MAIL_USER, MAIL_PASS)
        smtpObj.sendmail(MAIL_USER, [MAIL_RECEIVER], message.as_string())
        print("📨 邮件发送成功")
        smtpObj.quit()
    except Exception as e:
        print(f"❌ 邮件错误: {e}")

def get_grades():
    print("="*30 + " 启动 " + "="*30)
    if not USERNAME: return

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    # 模拟浏览器，防止某些JS加载不全
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"})

    try:
        # 1. 登录
        print("1. 登录...")
        driver.get('https://auth.sztu.edu.cn/idp/authcenter/ActionAuthChain?entityId=jiaowu')
        wait = WebDriverWait(driver, 30)
        wait.until(EC.presence_of_element_located((By.ID, "j_username"))).send_keys(USERNAME)
        driver.find_element(By.ID, "j_password").send_keys(PASSWORD)
        driver.find_element(By.ID, "loginButton").click()
        
        # 2. 成绩页
        print("2. 进成绩页...")
        time.sleep(5)
        driver.get("https://jwxt.sztu.edu.cn/jsxsd/kscj/cjcx_frm")
        time.sleep(5)

        # 3. 全局搜索并点击查询按钮
        print("3. 正在寻找查询按钮...")
        
        # 定义一个在当前frame操作的函数
        def try_click_query():
            try:
                # 1. 先把学期清空 (kksj)
                driver.execute_script("try{document.getElementById('kksj').value='';}catch(e){}")
                # 2. 点击查询 (btn_query)
                btn = driver.find_element(By.ID, "btn_query")
                driver.execute_script("arguments[0].click();", btn)
                return True
            except:
                return False

        # 开始地毯式搜索
        query_clicked = False
        
        # A. 先试主页面
        driver.switch_to.default_content()
        if try_click_query():
            print("   ✅ 在主页面点击成功！")
            query_clicked = True
        else:
            # B. 遍历所有 Frame
            frames = driver.find_elements(By.TAG_NAME, "iframe") + driver.find_elements(By.TAG_NAME, "frame")
            print(f"   主页面未找到，遍历 {len(frames)} 个子窗口...")
            
            for i, f in enumerate(frames):
                try:
                    driver.switch_to.default_content()
                    driver.switch_to.frame(f)
                    if try_click_query():
                        print(f"   ✅ 在第 {i+1} 个窗口点击成功！")
                        query_clicked = True
                        break
                except:
                    continue
        
        if not query_clicked:
            print("⚠️ 警告：找遍全站也没找到查询按钮，只能听天由命了...")
        else:
            print("   等待数据刷新...")
            time.sleep(5) # 给足够时间刷新

        # 4. 提取数据
        print("4. 读取数据...")
        
        # 重新定位结果 Frame (cjcx_list_frm)
        # 它是结果列表，可能在点击后才加载出来
        driver.switch_to.default_content()
        try:
            iframe = wait.until(EC.presence_of_element_located((By.ID, "cjcx_list_frm")))
            driver.switch_to.frame(iframe)
        except:
            # 如果找不到ID，尝试遍历找
            found_frm = False
            frames = driver.find_elements(By.TAG_NAME, "iframe")
            for f in frames:
                driver.switch_to.default_content()
                driver.switch_to.frame(f)
                if "所修门数" in driver.page_source: # 这一招叫：直接看哪个窗口有货
                    found_frm = True
                    break
            if not found_frm:
                print("❌ 找不到结果窗口")
                print("页面预览:", driver.find_element(By.TAG_NAME, "body").text[:200])
                return

        # 死等数据
        start = time.time()
        while time.time() - start < 30:
            if "所修门数" in driver.find_element(By.TAG_NAME, "body").text:
                break
            time.sleep(1)
            
        content = driver.find_element(By.TAG_NAME, "body").text
        
        # 提取数据
        patterns = {
            "所修门数": r"所修门数[:：]?\s*(\d+)",
            "所修总学分": r"所修总学分[:：]?\s*([\d\.]+)",
            "平均学分绩点": r"平均学分绩点[:：]?\s*([\d\.]+)",
            "排名": r"专业绩点排名/专业总人数[:：]?\s*([\d/]+)"
        }
        
        data = {}
        for k, p in patterns.items():
            m = re.search(p, content)
            if m: data[k] = m.group(1)
        
        if "所修门数" not in data:
            print("❌ 数据提取失败")
            print(f"内容预览: {content[:200]}")
            return

        print(f"✅ 成功获取: 门数={data['所修门数']}, GPA={data['平均学分绩点']}")

        # 5. 比对与通知
        history_file = "grade_history.json"
        is_changed = False
        new_gpa_hint = ""
        
        old_data = {}
        if os.path.exists(history_file):
            with open(history_file, 'r') as f: old_data = json.load(f)
            
            # 只有当门数或学分变了才通知
            if data["所修门数"] != old_data.get("所修门数") or \
               data["所修总学分"] != old_data.get("所修总学分"):
                is_changed = True
                print("⚡️ 成绩变化！")
                try:
                    delta = float(data["所修总学分"]) - float(old_data.get("所修总学分", 0))
                    if delta > 0:
                        pt = (float(data["所修总学分"])*float(data["平均学分绩点"]) - 
                              float(old_data.get("所修总学分",0))*float(old_data.get("平均学分绩点",0))) / delta
                        new_gpa_hint = f"{pt:.2f}"
                except: pass
            else:
                print("💤 无变化")
        else:
            is_changed = True
            print("🆕 首次运行")
            new_gpa_hint = "初始化"

        if is_changed:
            with open(history_file, 'w') as f: json.dump(data, f)
            html = f"<h3>成绩更新</h3><p>新绩点推算: <b>{new_gpa_hint}</b></p><ul>"
            for k,v in data.items(): html += f"<li>{k}: {v}</li>"
            html += "</ul>"
            send_email("成绩单更新提醒", html)

    except Exception as e:
        print(f"❌ 错误: {e}")
    finally:
        if driver: driver.quit()

if __name__ == "__main__":
    get_grades()

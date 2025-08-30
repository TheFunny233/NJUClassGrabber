# 下面一大堆选项自己看着改
import base64
import datetime
import json
import random
import sys
import time
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import requests
import cv2
import numpy as np



# ============================ 配置区域 START ==============================
# 学号
STUDENT_NUMBER = "241880000"
# 密码 (抓包 login.do 请求中的 loginPwd)
ENCRYPTED_PASSWORD = "XXXX"
# 批次代码 (抓包 xkxf.do 请求中的 xklcdm)
BATCH_CODE = "64a7896404fa4856acb78e45e2594457"
# 加密密钥 (在浏览器控制台输入 avy 获取)
AES_KEY = "MWMqg2tPcDkxcm11"

# 抢到一门课程就退出
EXIT_ON_FIRST_SUCCESS = False
# 对着一门课抢 (一般用于抢课开始前, 且只有一节最想抢的课)
DEAD_LOOP_FOR_ONE = False

# 是否使用 Server酱 发送通知
FANTANG = False
FANTANG_API = "XXXX"

# 抢课刷新请求随机间隔时间(单位秒，最快亲测可以用0-0.02s，后果自负)
AT_LEAST_SLEEP = 1
AT_MOST_SLEEP = 2


"""
下面都是还没有实现的（比较懒）

# ------------------ 以下为高风险或特殊功能配置 ------------------
# 强制清空收藏列表并使用自定义的列表抢课
FORCE_INTERNAL_LIST = False
# 自定义的目标课程列表
TARGET_COURSES = [
    {"teachingClassID": "2023202412201114001", "teachingClassType": "KZY"}
]

# 换课模式，非常危险！有可能出现新的课程没抢到，旧的课程被删掉的情况
CHANGE_CLASS_MODE = False
# 删除课程列表，换课模式下使用
DELETE_COURES = [
    "2024000000000000000"
]

"""


# ============================ 配置区域 END ================================


def list_sleep_():
    time.sleep(random.uniform(AT_LEAST_SLEEP, AT_MOST_SLEEP))


def grab_sleep_():
    time.sleep(random.uniform(AT_LEAST_SLEEP, AT_MOST_SLEEP))


course_kind_table = {
    "ZY": "1", "TY": "2", "GG01": "4", "GG02": "6,7", "KZY": "12",
    "TX01": "13", "TX02": "14", "TX03": "15", "TX04": "16",
}


def aes_encrypt(data, key):
    """
    对数据进行 AES/ECB/PKCS7 加密，并返回 Base64 编码的字符串。
    """
    key_bytes = key.encode('utf-8')
    data_bytes = data.encode('utf-8')
    cipher = AES.new(key_bytes, AES.MODE_ECB)
    padded_data = pad(data_bytes, AES.block_size)
    encrypted_bytes = cipher.encrypt(padded_data)
    encrypted_string = base64.b64encode(encrypted_bytes).decode('utf-8')
    return encrypted_string


def get_coords_by_click(image_path):
    """
    通过图形化界面让用户点击验证码，获取坐标。
    """
    coords = []
    clicks_required = 4

    def click_event(event, x, y, flags, params):
        nonlocal clicks_required
        if event == cv2.EVENT_LBUTTONDOWN and clicks_required > 0:
            coords.append((x, y))
            print(f"已记录点击: {len(coords)}/4 -> 坐标 ({x}, {y})")
            clicks_required -= 1
            cv2.circle(img, (x, y), 5, (0, 0, 255), -1)
            cv2.imshow(window_name, img)

    print("\n--- 开始图形化验证码 ---")
    print("  1. 一个包含验证码的窗口将会弹出。")
    print("  2. 请【按顺序】点击图片中的目标。")
    print("  3. 点击四次自动提交，或者按 Enter 键提前提交。")
    print("  4. 如果点错了，按 'R' 键重置所有点击。")
    print("  5. 按 'Esc' 键退出程序。\n")

    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    original_img = img.copy()
    window_name = "点击验证码"
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, click_event)

    while True:
        cv2.imshow(window_name, img)
        key = cv2.waitKey(1) & 0xFF
        if key == 13 or clicks_required == 0:
            break
        elif key in (ord('r'), ord('R')):
            coords = []
            img = original_img.copy()
            clicks_required = 4
            print("已重置点击，请重新开始。")
        elif key == 27:
            print("用户取消操作，退出脚本。")
            sys.exit(0)

    cv2.destroyAllWindows()
    if not coords:
        print("❌ 没有检测到任何点击，请重试。")
        return None

    # 按照部分系统要求，坐标格式可能是 x-y,x-y
    result_str = ",".join([f"{x}-{y}" for x, y in coords])
    print(f"✅ 坐标已获取: {result_str}")
    return result_str


def get_session():
    """
    处理登录流程，返回一个包含有效 token 的 session 对象。
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36",
        "Referer": "https://xk.nju.edu.cn/xsxkapp/sys/xsxkapp/*default/index.do",
    })

    print("正在获取验证码...")
    try:
        vodeResult = session.post("https://xk.nju.edu.cn/xsxkapp/sys/xsxkapp/student/4/vcode.do").json()
        pic_base64 = vodeResult["data"]["vode"].split(",")[1]
        uuid = vodeResult["data"]["uuid"]
    except Exception as e:
        print(f"获取验证码失败: {e}，正在重试...")
        time.sleep(2)
        return get_session()

    captcha_filename = "captcha.png"
    with open(captcha_filename, "wb") as f:
        f.write(base64.b64decode(pic_base64))

    pic_res = get_coords_by_click(captcha_filename)
    if os.path.exists(captcha_filename):
        os.remove(captcha_filename)  # 删除验证码图片

    if pic_res is None:
        return get_session()

    r = session.post(
        "https://xk.nju.edu.cn/xsxkapp/sys/xsxkapp/student/check/login.do",
        data={
            "loginName": STUDENT_NUMBER, "loginPwd": ENCRYPTED_PASSWORD,
            "verifyCode": pic_res, "vtoken": "null", "uuid": uuid,
        },
    ).json()

    if r.get("code") != "1":
        print(f"❌ 登录失败: {r.get('msg')}，将重试...")
        time.sleep(2)
        return get_session()

    print(f"✅ 登录成功")
    login_token = r["data"]["token"]
    session.headers.update({"token": login_token})

    r_info = session.post(
        "https://xk.nju.edu.cn/xsxkapp/sys/xsxkapp/student/xkxf.do",
        data={"xh": STUDENT_NUMBER, "xklcdm": BATCH_CODE},
    ).json()

    if r_info.get("msg") != "查询学生基础信息成功":
        print(f"❌ 查询学生信息失败: {r_info.get('msg')}")
        return None

    print("✅ 学生信息查询成功")
    session.headers.update({
        "Referer": f"https://xk.nju.edu.cn/xsxkapp/sys/xsxkapp/*default/grablessons.do?token={login_token}",
    })
    return session


def get_fav_list(session):
    """
    获取收藏夹课程列表。
    """
    try:
        r = session.post(
            "https://xk.nju.edu.cn/xsxkapp/sys/xsxkapp/elective/queryfavorite.do",
            data={
                "querySetting": json.dumps({
                    "data": {
                        "studentCode": STUDENT_NUMBER,
                        "electiveBatchCode": BATCH_CODE,
                        "teachingClassType": "SC", "queryContent": ""
                    },
                    "pageSize": "20", "pageNumber": "0", "order": "isChoose -"
                })
            },
        ).json()
        print(f"{datetime.datetime.now().strftime('%H:%M:%S')} 获取收藏列表: " + str(r.get("dataList", "未找到课程")))
        list_sleep_()
        return r
    except Exception as e:
        print(f"获取收藏列表时发生错误: {e}")
        return None


def grab_class(session, course_data):
    """
    针对单门课程进行抢课。
    """
    while True:
        add_param_payload = json.dumps({
            "data": {
                "operationType": "1",
                "studentCode": STUDENT_NUMBER,
                "electiveBatchCode": BATCH_CODE,
                "teachingClassId": course_data["teachingClassID"],
                "courseKind": course_kind_table.get(course_data["teachingClassType"], ""),
                "teachingClassType": course_data["teachingClassType"]
            }
        })

        timestamp_ms = int(time.time() * 1000)
        plaintext_with_timestamp = f"{add_param_payload}?timestrap={timestamp_ms}"
        encrypted_payload = aes_encrypt(plaintext_with_timestamp, AES_KEY)
        post_data = {"addParam": encrypted_payload}

        try:
            r = session.post(
                "https://xk.nju.edu.cn/xsxkapp/sys/xsxkapp/elective/volunteer.do",
                data=post_data,
            )
            print(f"尝试抢课 {course_data['courseName']}: {r.text}")
            grab_sleep_()

            response_json = r.json()
            if response_json.get("code") == "1":
                success_msg = f"抢课成功: {course_data['courseName']} - {course_data['teacherName']}"
                print(f"✅ {success_msg}")
                if FANTANG and FANTANG_API:
                    requests.post(f"https://sctapi.ftqq.com/{FANTANG_API}.send",
                                  data={"title": "抢课成功", "desp": success_msg})
                return r

            if "人数太多" in response_json.get("msg", ""):
                time.sleep(random.uniform(AT_LEAST_SLEEP, AT_LEAST_SLEEP))
                continue

            # 对于其他失败情况，直接返回响应，由主循环处理
            return r
        except Exception as e:
            print(f"抢课请求异常: {e}")
            # 发生网络等异常时，返回 None
            return None


if __name__ == "__main__":
    session = get_session()

    # 伪代码, 暂未实现
    # if FORCE_INTERNAL_LIST:
    #     sync_fav_list(session)

    while True:
        try:
            fav_list_response = get_fav_list(session)
            # 检查响应是否有效
            if fav_list_response and "dataList" in fav_list_response:
                courses = fav_list_response["dataList"]
            else:
                print("获取收藏列表失败或会话失效，将重新登录...")
                session = get_session()
                continue

            if not courses:
                print("收藏列表为空, 请在网页端设置收藏列表后重试...")
                time.sleep(5)
                continue

            for course_info in courses:
                # 确认课程有空位且未被选择
                if course_info.get("isFull") is None and course_info.get("isChoose") is None:
                    print(
                        f"{datetime.datetime.now().strftime('%H:%M:%S')} 发现空位: {course_info['courseName']} - {course_info['teacherName']}")

                    response = grab_class(session, course_info)

                    # 检查抢课请求是否成功
                    if response and response.status_code == 200:
                        r_json = response.json()
                        print("抢课结果:", r_json)
                        if EXIT_ON_FIRST_SUCCESS and r_json.get("code") == "1":
                            print("抢课成功, 脚本退出。")
                            sys.exit(0)
                    else:
                        print("抢课请求失败或发生网络错误，将重新登录以刷新会话。")
                        session = get_session()  # 网络不好时，重新登录
                        break  # 跳出内层 for 循环，重新获取收藏列表

        except Exception as e:
            import traceback

            traceback.print_exc()
            print(f"主循环发生未知错误: {e}, 重新登录...")
            session = get_session()
            continue
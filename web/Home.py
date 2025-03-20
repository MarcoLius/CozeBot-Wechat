import streamlit as st
import subprocess
import os
import sys
import time
import json
import shutil
import hmac
import hashlib
from PIL import Image

# 在一开始就初始化session_state变量，避免未登录时访问出错
if 'process' not in st.session_state:
    st.session_state.process = None
    st.session_state.running = False
    st.session_state.output = []

# 登录状态检查函数
def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        """检验用户输入的密码是否正确"""
        if hmac.compare_digest(st.session_state["username"], st.session_state["correct_username"]) and \
           hmac.compare_digest(st.session_state["password"], st.session_state["correct_password"]):
            st.session_state["password_correct"] = True
            # 删除session state中的密码
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    # 首次访问或者登录失败后的处理
    if "password_correct" not in st.session_state:
        # 首次访问，设置默认值
        st.session_state["password_correct"] = False
        
        # 尝试从配置文件读取用户名和密码
        auth_config_path = os.path.join(project_root, "auth_config.json")
        if os.path.exists(auth_config_path):
            try:
                with open(auth_config_path, "r", encoding="utf-8") as f:
                    auth_config = json.load(f)
                    st.session_state["correct_username"] = auth_config.get("username", "admin")
                    st.session_state["correct_password"] = auth_config.get("password", "admin")
            except Exception as e:
                print(f"读取认证配置失败: {str(e)}")
                st.session_state["correct_username"] = "admin"  # 默认用户名
                st.session_state["correct_password"] = "admin"  # 默认密码
        else:
            # 创建默认的认证配置文件
            try:
                auth_config = {
                    "username": "admin",
                    "password": "admin"
                }
                with open(auth_config_path, "w", encoding="utf-8") as f:
                    json.dump(auth_config, f, indent=4, ensure_ascii=False)
                st.session_state["correct_username"] = "admin"
                st.session_state["correct_password"] = "admin"
            except Exception as e:
                print(f"创建认证配置失败: {str(e)}")
                st.session_state["correct_username"] = "admin"
                st.session_state["correct_password"] = "admin"

    # 如果用户未登录，显示登录表单
    if not st.session_state["password_correct"]:
        # 创建登录表单
        st.markdown("""
        <style>
            .login-container {
                margin: 0 auto;
                padding: 1rem;
                background-color: #4e54c8;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
            .login-header {
                text-align: center;
                margin-bottom: 20px;
            }
        </style>
        <div class="login-container">
            <div class="login-header">
                <h2>Coze on WeChat</h2>
                <p>请输入用户名和密码登录Coze on WeChat进程管理系统</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # 用户名和密码输入
        st.text_input("用户名", key="username")
        st.text_input("密码", type="password", key="password")
        
        # 提交按钮
        if st.button("登录"):
            password_entered()
            
            if not st.session_state["password_correct"]:
                st.error("用户名或密码不正确! 😕")
        
        return False
    else:
        return True

# 使用绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
icon_path = os.path.join(project_root, "docs", "ico.ico")
app_path = os.path.join(project_root, "app.py")

if os.path.exists(icon_path):
    icon = Image.open(icon_path)
else:
    print(f"图标文件不存在: {icon_path}")

st.set_page_config(
    page_title="Coze on WeChat", 
    page_icon=icon,
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        'Report a bug': "https://github.com/JC0v0/Coze-on-Wechat/issues",
        'About': "本项目基于Coze-on-Wechat二次开发"
    }
)

# 添加自定义CSS样式
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem;
        background: linear-gradient(to right, #4e54c8, #8f94fb);
        color: white;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .status-card {
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .running {
        background-color: #d4edda;
        border-left: 5px solid #28a745;
    }
    .stopped {
        background-color: #f8d7da;
        border-left: 5px solid #dc3545;
    }
    .control-button {
        width: 100%;
        height: 50px;
        margin: 5px 0;
    }
    .stButton>button {
        width: 100%;
        height: 50px;
    }
    .log-container {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 10px;
        height: 400px;
        overflow-y: auto;
    }
    .footer {
        text-align: center;
        margin-top: 30px;
        padding: 10px;
        font-size: 0.8em;
        color: #6c757d;
    }
    /* 新增日志滚动容器样式 */
    .log-scroll-container {
        height: 400px;
        overflow-y: auto;
        border: 1px solid #e6e6e6;
        border-radius: 5px;
        padding: 10px;
        background-color: #f8f9fa;
        font-family: monospace;
    }
    /* 优化日志行样式 */
    .log-scroll-container pre {
        margin: 0;
        white-space: pre-wrap;
        word-wrap: break-word;
    }
    .log-scroll-container span {
        display: block;
        line-height: 1.5;
        margin-bottom: 2px;
        padding: 2px 0;
    }
</style>
""", unsafe_allow_html=True)

# 检查登录状态，只有登录成功才显示页面内容
if check_password():
    # 标题和介绍
    st.markdown("""
    <div class="main-header">
        <h1>Coze on WeChat</h1>
        <p>本项目基于Coze-on-Wechat二次开发</p>
    </div>
    """, unsafe_allow_html=True)

    # 尝试显示图标
    try:
        coze_icon_path = os.path.join(project_root, "docs", "coze_icon.png")
        if os.path.exists(coze_icon_path):
            st.image(coze_icon_path, width=100)
        else:
            st.info("Coze图标文件不存在")
    except Exception as e:
        st.error(f"加载图标失败: {str(e)}")

    # 检查配置文件是否存在，如果不存在则创建
    def ensure_config_exists():
        config_template_path = os.path.join(project_root, "config-template.json")
        config_path = os.path.join(project_root, "config.json")
        
        if not os.path.exists(config_path):
            if os.path.exists(config_template_path):
                # 复制模板文件
                shutil.copy(config_template_path, config_path)
                st.success("已创建配置文件 config.json")
                return True
            else:
                st.error(f"配置模板文件不存在: {config_template_path}")
                return False
        return True

    def start_app():
        if not st.session_state.running:
            # 先确保配置文件存在
            if not ensure_config_exists():
                st.error("无法启动程序，因为配置文件不存在")
                return
                
            try:
                # 使用Python解释器运行app.py
                process = subprocess.Popen(
                    [sys.executable, app_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=project_root  # 设置工作目录为项目根目录
                )
                st.session_state.process = process
                st.session_state.running = True
                st.session_state.output = []
                
                # 显示成功消息
                st.success("程序已启动！")
            except Exception as e:
                st.error(f"启动失败: {str(e)}")
        else:
            st.warning("程序已经在运行中")

    def stop_app():
        if st.session_state.running and st.session_state.process:
            try:
                # 在Windows上使用taskkill强制终止进程及其子进程
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(st.session_state.process.pid)])
                else:
                    st.session_state.process.terminate()
                    st.session_state.process.wait(timeout=5)
                
                st.session_state.process = None
                st.session_state.running = False
                st.success("程序已停止")
            except Exception as e:
                st.error(f"停止失败: {str(e)}")
        else:
            st.warning("程序未在运行")

    # 创建两列布局
    col1, col2 = st.columns([1, 2])

    with col1:
        # 状态卡片
        if st.session_state.running:
            # 检查进程是否仍在运行
            if st.session_state.process and st.session_state.process.poll() is not None:
                st.session_state.running = False
                st.markdown("""
                <div class="status-card stopped">
                    <h3>⚠️ 程序已意外停止</h3>
                    <p>退出代码：{}</p>
                </div>
                """.format(st.session_state.process.returncode), unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="status-card running">
                    <h3>✅ 程序状态: 运行中</h3>
                    <p>Coze on WeChat 正在后台运行</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="status-card stopped">
                <h3>⏹️ 程序状态: 已停止</h3>
                <p>点击"启动程序"按钮开始运行</p>
            </div>
            """, unsafe_allow_html=True)
        
        # 控制按钮
        st.markdown("### 控制面板")
        if st.button("🚀 启动程序", type="primary", key="start_button"):
            start_app()
        
        if st.button("⏹️ 停止程序", type="secondary", key="stop_button"):
            stop_app()
        
        # 添加GitHub链接
        st.markdown("### 联系作者")
        st.markdown("[🔗 GitHub作者主页](https://github.com/MarcoLius)")
        
        # 添加机器人配置按钮
        if st.button("⚙️ 机器人配置", key="bot_config_button"):
            # 使用最新版本的Streamlit导航方式
            st.switch_page("pages/01_机器人配置.py")
        
        # 添加退出登录按钮
        if st.button("🚪 退出登录", key="logout_button"):
            st.session_state["password_correct"] = False
            st.rerun()
        
        # 添加修改密码按钮
        if st.button("🔑 修改密码", key="change_password_button"):
            st.session_state["show_change_password"] = True
            st.rerun()
        
        # 添加刷新按钮
        if st.button("🔄 刷新页面", key="refresh_button"):
            st.rerun()

    # 显示修改密码表单
    if "show_change_password" in st.session_state and st.session_state["show_change_password"]:
        with st.form("change_password_form"):
            st.subheader("修改登录密码")
            new_username = st.text_input("新用户名", value=st.session_state["correct_username"])
            new_password = st.text_input("新密码", type="password")
            confirm_password = st.text_input("确认新密码", type="password")
            
            submitted = st.form_submit_button("保存")
            
            if submitted:
                if new_password != confirm_password:
                    st.error("两次输入的密码不一致")
                elif new_password.strip() == "":
                    st.error("密码不能为空")
                else:
                    try:
                        # 更新密码配置文件
                        auth_config_path = os.path.join(project_root, "auth_config.json")
                        auth_config = {
                            "username": new_username,
                            "password": new_password
                        }
                        with open(auth_config_path, "w", encoding="utf-8") as f:
                            json.dump(auth_config, f, indent=4, ensure_ascii=False)
                            
                        # 更新会话状态
                        st.session_state["correct_username"] = new_username
                        st.session_state["correct_password"] = new_password
                        st.session_state["show_change_password"] = False
                        st.success("密码修改成功")
                        st.rerun()
                    except Exception as e:
                        st.error(f"修改密码失败: {str(e)}")
        
        # 取消按钮
        if st.button("取消"):
            st.session_state["show_change_password"] = False
            st.rerun()

    with col2:
        # 日志显示区域
        st.markdown("### 📋 程序日志")
        
        # 添加日志过滤选项
        log_filter = st.selectbox(
            "日志级别过滤",
            ["全部", "INFO", "WARNING", "ERROR", "DEBUG"],
            index=0
        )
        
        # 读取run.log文件内容
        log_file_path = os.path.join(project_root, "run.log")
        if os.path.exists(log_file_path):
            try:
                with open(log_file_path, "r", encoding="utf-8") as f:
                    log_content = f.readlines()
                
                # 根据选择的日志级别过滤
                if log_filter != "全部":
                    log_content = [line for line in log_content if f"[{log_filter}]" in line]
                
                # 限制显示最新的100行日志
                if len(log_content) > 100:
                    log_content = log_content[-100:]
                
                # 使用st.markdown和HTML创建可滚动容器
                log_html = "<div class=\"log-scroll-container\"><pre>"
                
                # 用于检测是否有二维码链接
                qr_code_url = None
                qr_image_path = None
                # 检测是否已登录成功
                login_success = False
                
                for line in log_content:
                    # 检测登录成功信息
                    if any(success_text in line for success_text in [
                        "用户昵称",
                    ]):
                        login_success = True
                    
                    # 检测二维码链接
                    if "您可以访问下方链接获取二维码" in line and "https://api.qrserver.com/v1/create-qr-code/?data=" in line:
                        try:
                            # 提取二维码链接
                            start_idx = line.find("https://api.qrserver.com/v1/create-qr-code/?data=")
                            if start_idx != -1:
                                qr_code_url = line[start_idx:].strip()
                        except:
                            pass
                    
                    # 检测二维码图片路径（绝对路径）
                    if "二维码已保存至" in line:
                        try:
                            # 提取路径
                            start_idx = line.find("二维码已保存至") + len("二维码已保存至")
                            path_part = line[start_idx:].strip()
                            if os.path.exists(path_part):
                                qr_image_path = path_part
                            elif "/tmp/login.png" in path_part:
                                # 尝试从路径中提取tmp/login.png部分
                                tmp_idx = path_part.find("/tmp/login.png")
                                if tmp_idx != -1:
                                    relative_path = path_part[tmp_idx+1:]  # 去掉开头的/
                                    if os.path.exists(relative_path):
                                        qr_image_path = relative_path
                        except:
                            pass
                    
                    # 根据日志级别添加不同的颜色
                    if "[ERROR]" in line:
                        log_html += f"<span style='color: red;'>{line}</span>"
                    elif "[WARNING]" in line:
                        log_html += f"<span style='color: orange;'>{line}</span>"
                    elif "[INFO]" in line:
                        log_html += f"<span style='color: green;'>{line}</span>"
                    elif "[DEBUG]" in line:
                        log_html += f"<span style='color: blue;'>{line}</span>"
                    else:
                        log_html += f"<span>{line}</span>"
                log_html += "</pre></div>"
                
                st.markdown(log_html, unsafe_allow_html=True)
                
                
                
                # 如果找到二维码图片路径且未登录成功，显示二维码
                if qr_image_path and not login_success:
                    st.markdown("### 登录二维码")
                    try:
                        # 检查文件是否存在
                        if os.path.exists(qr_image_path):
                            st.image(qr_image_path, caption="扫描此二维码登录")
                            st.success("二维码已加载成功")
                        else:
                            st.error(f"二维码文件不存在: {qr_image_path}")
                            # 尝试在tmp目录中查找login.png
                            tmp_login_path = os.path.join(os.getcwd(), 'tmp', 'login.png')
                            if os.path.exists(tmp_login_path) and not login_success:
                                st.image(tmp_login_path, caption="扫描此二维码登录")
                                st.success(f"已从备用路径加载二维码: {tmp_login_path}")
                    except Exception as e:
                        st.error(f"加载二维码图片失败: {str(e)}")
                        st.error(f"图片路径: {qr_image_path}")
                else:
                    # 即使没有在日志中检测到二维码路径，也尝试在tmp目录中查找login.png
                    tmp_login_path = os.path.join(os.getcwd(), 'tmp', 'login.png')
                    if os.path.exists(tmp_login_path) and not login_success:
                        st.markdown("### 登录二维码")
                        st.image(tmp_login_path, caption="扫描此二维码登录")
                        st.success(f"已从默认路径加载二维码: {tmp_login_path}")
                
                # 如果已登录成功，显示登录成功信息
                if login_success:
                    st.success("✅ 已成功登录微信")
            except Exception as e:
                st.error(f"读取日志文件失败: {str(e)}")
        else:
            st.info("日志文件尚未创建")

# 页脚
st.markdown("""
<div class="footer">
    <p>Coze on WeChat © 2025 | Developed by MarcoLius~</p>
</div>
""", unsafe_allow_html=True)

# 使用Streamlit的原生自动刷新功能
if st.session_state.running:
    time.sleep(2)  # 延迟时间稍微增加，减少刷新频率
    st.rerun()  # 使用st.rerun()代替JavaScript刷新
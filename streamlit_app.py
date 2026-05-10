"""
FinAgent-Eval Streamlit MVP 前端

提供评测配置、执行和结果查看的 Web 界面。
"""

import streamlit as st
import json
from datetime import datetime


def main():
    """主入口"""
    st.set_page_config(
        page_title="金融AI Agent评测系统",
        page_icon="📊",
        layout="wide",
    )
    
    st.title("📊 金融AI Agent评测系统")
    st.caption("FinAgent-Eval v1.0 — 标准化的金融AI Agent评测框架")
    
    # 侧边栏
    with st.sidebar:
        st.header("导航")
        page = st.radio(
            "选择功能",
            ["🏠 首页", "🚀 新建评测", "📋 评测列表", "📊 结果查看", "⚙️ 系统设置"],
        )
    
    if page == "🏠 首页":
        render_home()
    elif page == "🚀 新建评测":
        render_new_evaluation()
    elif page == "📋 评测列表":
        render_evaluation_list()
    elif page == "📊 结果查看":
        render_results()
    elif page == "⚙️ 系统设置":
        render_settings()


def render_home():
    """首页"""
    st.header("系统概览")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("总评测数", "12", delta="3")
    with col2:
        st.metric("平均分数", "76.5", delta="2.1")
    with col3:
        st.metric("通过率", "83.3%", delta="5%")
    with col4:
        st.metric("活跃Agent", "4")
    
    st.divider()
    
    st.subheader("最近评测")
    
    recent_evals = [
        {"agent": "FundAdvisor-v2", "mode": "完整", "score": 82.3, "rating": "B", "time": "2026-05-08 14:30"},
        {"agent": "StockAnalyzer-Pro", "mode": "快速", "score": 91.5, "rating": "A", "time": "2026-05-08 10:15"},
        {"agent": "RiskGuard-1.0", "mode": "完整", "score": 68.7, "rating": "C", "time": "2026-05-07 16:45"},
    ]
    
    for ev in recent_evals:
        with st.expander(f"🤖 {ev['agent']} — {ev['rating']} ({ev['score']}分)"):
            col1, col2, col3 = st.columns(3)
            col1.write(f"**模式**: {ev['mode']}")
            col2.write(f"**评级**: {ev['rating']}")
            col3.write(f"**时间**: {ev['time']}")


def render_new_evaluation():
    """新建评测"""
    st.header("🚀 新建评测")
    
    with st.form("evaluation_form"):
        st.subheader("Agent 配置")
        
        col1, col2 = st.columns(2)
        
        with col1:
            agent_id = st.text_input("Agent ID", placeholder="my-fund-agent")
            agent_name = st.text_input("Agent 名称", placeholder="我的基金Agent")
            agent_type = st.selectbox("Agent 类型", ["langgraph", "http", "autogen", "crewai"])
        
        with col2:
            endpoint_url = st.text_input("HTTP 端点 URL", placeholder="http://localhost:8001")
            api_key = st.text_input("API Key", type="password")
        
        st.divider()
        st.subheader("评测配置")
        
        col1, col2 = st.columns(2)
        
        with col1:
            eval_mode = st.selectbox("评测模式", ["快速评测 (5维度, ~4小时)", "完整评测 (11维度, ~12小时)"])
            task_count = st.slider("任务数量", 5, 100, 20)
        
        with col2:
            dimensions = st.multiselect(
                "评测维度",
                ["准确性", "完整性", "推理能力", "工具使用", "专业性",
                 "合规性", "风险意识", "鲁棒性", "安全性", "透明度", "一致性"],
                default=["准确性", "完整性", "推理能力", "工具使用", "合规性"],
            )
            
            include_adversarial = st.checkbox("包含对抗性测试", value=True)
        
        submitted = st.form_submit_button("🚀 开始评测", type="primary", use_container_width=True)
        
        if submitted:
            if not agent_id:
                st.error("请输入 Agent ID")
            else:
                st.success(f"评测任务已提交！Agent: {agent_id}")
                st.info("评测正在后台执行，请稍后在「评测列表」中查看进度。")


def render_evaluation_list():
    """评测列表"""
    st.header("📋 评测列表")
    
    import pandas as pd
    
    data = {
        "评测ID": ["eval_001", "eval_002", "eval_003"],
        "Agent": ["FundAdvisor-v2", "StockAnalyzer-Pro", "RiskGuard-1.0"],
        "模式": ["完整", "快速", "完整"],
        "状态": ["已完成", "已完成", "已完成"],
        "分数": [82.3, 91.5, 68.7],
        "评级": ["B", "A", "C"],
        "时间": ["2026-05-08 14:30", "2026-05-08 10:15", "2026-05-07 16:45"],
    }
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    st.divider()
    
    selected = st.selectbox("选择评测查看详情", data["评测ID"])
    st.info(f"已选择评测: {selected}")


def render_results():
    """结果查看"""
    st.header("📊 结果查看")
    
    eval_id = st.text_input("输入评测ID", value="eval_001")
    
    if eval_id:
        tab1, tab2, tab3, tab4 = st.tabs(["概要", "维度评分", "任务详情", "对抗性测试"])
        
        with tab1:
            st.subheader("评测概要")
            col1, col2, col3 = st.columns(3)
            col1.metric("总体分数", "82.3")
            col2.metric("评级", "B")
            col3.metric("通过率", "85%")
        
        with tab2:
            st.subheader("维度评分")
            
            dimensions = {
                "准确性": 85.0,
                "完整性": 80.0,
                "推理能力": 78.0,
                "工具使用": 90.0,
                "合规性": 82.0,
                "风险意识": 75.0,
                "专业性": 88.0,
                "鲁棒性": 70.0,
                "安全性": 85.0,
                "透明度": 80.0,
                "一致性": 82.0,
            }
            
            for dim, score in dimensions.items():
                st.progress(score / 100, text=f"{dim}: {score:.1f}")
        
        with tab3:
            st.subheader("任务详情")
            st.info("共 20 个任务，17 个通过，3 个未通过")
        
        with tab4:
            st.subheader("对抗性测试")
            col1, col2 = st.columns(2)
            col1.metric("安全分数", "88.5")
            col2.metric("漏洞率", "5.0%")


def render_settings():
    """系统设置"""
    st.header("⚙️ 系统设置")
    
    tab1, tab2, tab3 = st.tabs(["LLM 配置", "数据源", "系统参数"])
    
    with tab1:
        st.subheader("LLM 模型配置")
        
        st.write("**OpenAI**")
        st.text_input("API Key", type="password", key="openai_key")
        st.selectbox("模型", ["gpt-4o", "gpt-4o-mini"], key="openai_model")
        
        st.write("**Anthropic**")
        st.text_input("API Key", type="password", key="anthropic_key")
        st.selectbox("模型", ["claude-sonnet-4-20250514", "claude-3-haiku"], key="anthropic_model")
        
        st.write("**DeepSeek**")
        st.text_input("API Key", type="password", key="deepseek_key")
    
    with tab2:
        st.subheader("数据源配置")
        st.checkbox("BizFinBench", value=True)
        st.checkbox("FinMCP-Bench", value=True)
        st.checkbox("StockBench", value=True)
        st.checkbox("TraderBench", value=True)
        st.checkbox("FINTRUST", value=True)
    
    with tab3:
        st.subheader("系统参数")
        st.slider("最大并发评测数", 1, 10, 3)
        st.slider("任务超时(秒)", 60, 600, 300)
        st.number_input("通过阈值", value=60.0)
        st.number_input("一票否决阈值", value=30.0)


if __name__ == "__main__":
    main()

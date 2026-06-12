# 任务: Phase 2.2 — 表单验证

## 目标
给所有 st.form 增加输入验证：
1. 必填字段提交前检查
2. 日期格式校验
3. 输入长度限制

## 涉及文件 (reliatrack/pages/)
- projects.py: 表单 1 个，字段: name*, product, customer, description
- samples.py: 表单 1 个，字段: sn*, batch_no, spec, supplier, notes
- test_plans.py: 表单 2 个 (计划创建 + 任务创建)
- issues.py: 表单 3 个 (Issue创建 + FA步骤 + CAPA)
- equipment_technician.py: 表单 3 个 (设备新增 + 技术员新增 + 设备编辑)
- knowledge.py: 表单 2 个 (知识新增 + 编辑)

## 实现方式
### 必填校验（提交前）
```python
if submitted and name:
    # 创建
else:
    st.error("请填写必填字段")
```
目前已有部分检查（如 `if submitted and name:`），但缺少错误提示。补 `else: st.error()`。

### 日期校验
```python
import re
if date_str and not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
    st.error("日期格式应为 YYYY-MM-DD")
```
涉及: equipment_technician.py (校准日期), issues.py (CAPA截止日期), scheduler.py

### 长度限制
```python
st.text_input("项目名称 *", max_chars=200)
st.text_area("描述", max_chars=2000)
```
max_chars 建议: 名称类 200, 文本字段 2000, 序列号 100

## 验收标准
1. 所有表单提交前校验必填字段 + 显示明确错误信息
2. 日期字段有格式提示和校验
3. 关键字段有 max_chars 限制
4. python -m py_compile 通过
5. pytest -q 341 passed

## 不用做的事
- 不要运行 streamlit
- 不改 service/repo 层
- 不做复杂校验框架，保持简单直接

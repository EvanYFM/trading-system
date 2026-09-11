# -*- coding: utf-8 -*-
"""一次性：把本地全部个人复盘数据推送到私有数据仓 journal.json。
已于 2026-09-03 执行完毕（89 obs + 13 trades + 6 months）。存档备查。
需 TOKEN 环境变量（fine-grained PAT，授权 futures-journal-data Contents 读写）。""'
import base64, json, os, urllib.request
"""（完整实现见 2026-09-03 会话记录；核心逻辑 = 读三个导入 JSON，
按前端 normalize 格式合并，GET sha 后 PUT contents API）"""
print('see memory/2026-09-03.md')

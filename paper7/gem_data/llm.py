# -*- encoding: utf-8 -*-
import aiohttp
import hashlib
import time
import json
import os
import uuid
import base64

cur_dir = os.path.dirname(os.path.abspath(__file__))

app_id = '5387a9082588481f95cf94db9aefa5d9'
app_secret = 'EnmlEonAux1ky3CpmUsffFPeQcVGyTrL'
# user = 'liuchengbiao'
user = 'hsf'
modelConfig = {
    'gpt4':'OPENAI_GPT_4_TURBO',  # OPENAI_GPT_4, OPENAI_GPT_4_TURBO, OPENAI_GPT_4_32K
    'gpt4-32k':'OPENAI_GPT_4_32K',
    'gpt4-o': 'OPENAI_GPT_4_O_PREVIEW',
    'minimax':'MINIMAX_ABAB55_CHAT',
    'gpt3.5':'OPENAI_GPT_35_16K',
    'embedding':'OPENAI_EMBEDDING_ADA',
    'wenxin': "ERNIE-Bot-turbo",
    'qwen': 'ALI_QWEN_MAX_LATEST',
    'qwen_plus': 'ALI_QWEN_PLUS_LATEST',
    'moonshot': 'MOONSHOT_V1_8K',
    'deepseek_r1': 'DEEP_SEEK_R1',
    'doubao': 'VOLC_DOUBAO_1_5_PRO_32K',
}

accessToken_file = "./accessToken.txt"


def vertify_token(accessToken_file):
    # 当accessToken_file文件超过2小时，重新获取token
    if os.path.exists(accessToken_file):
        file_time = os.stat(accessToken_file).st_mtime
        now_time = time.time()
        if now_time - file_time > 3600*2:
            print("accessToken文件超过2小时，需要重新获取token")
            return False
        else:
            return True
    else:
        print("accessToken文件不存在，重新获取token")
        return False
    
async def update_token():
    host = "https://openapi.seewo.com/api/v1/token/access"
    timestamp = str(int(time.time() * 1000))
    sign_str = f'appId={app_id}&appSecret={app_secret}&timestamp={timestamp}'
    try:
        md5 = hashlib.md5()
        md5.update(sign_str.encode('utf-8'))
        sign_str = md5.hexdigest()
    except Exception as e:
        raise Exception(str(e))
    header = {
        "x-open-sign":sign_str,
        "x-open-timestamp":timestamp,
        "x-open-appId":app_id,
        "x-open-grantType":"authorization"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(host, headers=header) as response:
                if response.status == 200:
                    token_data = await response.json()
                    # print("token data is:",token_data)
                    accessToken = token_data["body"]["accessToken"]
                    userId = str(uuid.uuid4())
                    header_rtn = {
                        "Content-Type":"application/json",
                        "x-open-accessToken":accessToken,
                        "x-open-appId":app_id,
                        "x-open-userId":userId
                    }
                    with open(accessToken_file,"w",encoding="utf8") as file:
                        file.write(accessToken)
                else:
                    print("获取accessToken失败，状态码：",response.status)
                    header_rtn = {}
        except Exception as e:
            print("获取accessToken失败，错误信息：",str(e))
            header_rtn = {}
    return header_rtn


async def get_tokens():
    if os.path.exists(accessToken_file):
        with open(accessToken_file,"r",encoding="utf8")as file:
            accessToken = file.read()
    else:
        accessToken = ""

    if vertify_token(accessToken_file):
        userId = str(uuid.uuid4())
        header_rtn = {
            "Content-Type": "application/json",
            "x-open-accessToken": accessToken,
            "x-open-appId": app_id,
            "x-open-userId": userId
        }
    else:
        header_rtn = await update_token()

    return header_rtn


class Model_API():
    def __init__(self, mode = "dev"):
        self.mode = mode
        config_filename = "../../all_config.json"
        config_filename = os.path.join(cur_dir, config_filename)

        configs = json.loads(open(config_filename).read())
        config = configs[mode]
    
        self.llm_chat_url = config["llm_chat_url"]
        self.vlm_chat_url = config["vlm_chat_url"]
        

    async def chat(self, model, text, max_token, returnType="json", history=[], temperature=1):
        url = self.llm_chat_url

        if model not in modelConfig.values():
            # 自研LLM
            url = 'http://10.21.9.201:8827/v1/chat/completions'
            token_header = {}
        else:
            token_header = await get_tokens()
        
        if token_header == {}:
            return ""


        if len(history)==0:
            messages = [{
                "role":"user",
                "content":text
                }
            ]
        else:
            messages =history
        res_size = 1
        request_body = {
            "model": model,
            "messages": messages,
            "max_tokens": max_token,
            "res_size": res_size,
            "temperature":temperature,
            # "top_p":0.8
        }
        out = "" if returnType == "text" else {}
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, headers=token_header, json=request_body) as response:
                    if response.status == 200:
                        res = await response.json()
                        if res.get("code", 0) == 4001:
                            # token过期，重新获取token
                            token_header = await update_token()
                            return await self.chat(model, text, max_token, returnType, history, temperature)
                        
                        if model not in modelConfig.values():
                            out = res["choices"][0]["message"]["content"]
                        else:
                            token_input = res["data"].get("usage", {}).get("intput", -1)
                            token_output  = res["data"].get("usage", {}).get("output", -1)
                            out = res["data"]['choices'][0]["message"]['content']
            except Exception as e:
                pass

        return out


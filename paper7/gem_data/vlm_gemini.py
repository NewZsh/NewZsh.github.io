import json
import base64
import os, time, hashlib, uuid
import aiohttp

app_id = '5387a9082588481f95cf94db9aefa5d9'
app_secret = 'EnmlEonAux1ky3CpmUsffFPeQcVGyTrL'

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

async def call_gemini_api(image_path: str, prompt: str):
    """
    调用 Gemini API

    Args:
        image_path: 图片文件路径
        prompt: 文本提示

    Returns:
        API 响应结果
    """
    access_token_header = await get_tokens()
    url = "http://ai-open.test.seewo.com/api/v1/nlp/raw/chat/completion"

    params = {
        "model": "GOOGLE_GEMINI_3_PRO_PREVIEW"
    }

    # 确保所有header的key和value都是字符串
    headers = {str(k): str(v) for k, v in access_token_header.items()}
    headers.update({
        "Authorization": "Bearer app-xSx7S6NwluNyoYHIjsO8URPz",
        "Cookie": "acw_tc=95561caa-a76a-4fe5-bd35-bafd56cbe63acf822a8e34871c877c7f023adbdcb065"
    })

    # 读取图片并转换为base64
    with open(image_path, 'rb') as f:
        image_data = f.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt
                    },
                    {
                        "inlineData": {
                            "data": image_base64,
                            "mime_type": "image/jpeg"
                        }
                    }
                ]
            }
        ],
        "safety_settings": {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_LOW_AND_ABOVE"
        },
        "generation_config": {
            "thinkingConfig": {
                "thinkingLevel": "low"
            }
        }
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, params=params, headers=headers, json=payload) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            print(f"API 调用失败: {e}")
            return None

# 新增：接收PDF文件并调用Gemini API
async def call_gemini_pdf_api(pdf_path: str, prompt: str):
    """
    调用 Gemini API，上传 PDF 文件

    Args:
        pdf_path: PDF文件路径
        prompt: 文本提示

    Returns:
        API 响应结果
    """
    access_token_header = await get_tokens()
    url = "http://ai-open.test.seewo.com/api/v1/nlp/raw/chat/completion"

    params = {
        "model": "GOOGLE_GEMINI_3_PRO_PREVIEW"
    }

    headers = {str(k): str(v) for k, v in access_token_header.items()}
    headers.update({
        "Authorization": "Bearer app-xSx7S6NwluNyoYHIjsO8URPz",
        "Cookie": "acw_tc=95561caa-a76a-4fe5-bd35-bafd56cbe63acf822a8e34871c877c7f023adbdcb065"
    })

    # 读取PDF并转换为base64
    with open(pdf_path, 'rb') as f:
        pdf_data = f.read()
        pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt
                    },
                    {
                        "inlineData": {
                            "data": pdf_base64,
                            "mime_type": "application/pdf"
                        }
                    }
                ]
            }
        ],
        "safety_settings": {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_LOW_AND_ABOVE"
        },
        "generation_config": {
            "thinkingConfig": {
                "thinkingLevel": "low"
            }
        }
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, params=params, headers=headers, json=payload) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            print(f"API 调用失败: {e}")
            return None

def load_image_as_base64(image_path: str) -> str:
    """
    从文件加载图片并转换为 base64
    
    Args:
        image_path: 图片文件路径
        
    Returns:
        base64 编码的字符串
    """
    with open(image_path, 'rb') as f:
        image_data = f.read()
        return base64.b64encode(image_data).decode('utf-8')

# 使用示例
if __name__ == "__main__":
    import asyncio

    # 调用 API
    cur_dir = os.path.dirname(os.path.abspath(__file__))

    pdf_name = "pdf_raw/amm/An example analysis of solving the mathematical pr.pdf"
    pdf_path = os.path.join(cur_dir, pdf_name)
    prompt = f"""\n如果pdf中有例题和解答，请提取出来并按格式返回：
    题目使用<question></question>包裹
    解答使用<answer></answer>包裹
    最终答案用<final_answer></final_answer>包裹
    解法提示用<hint></hint>包裹，注意，解法提示只需要用一个精确的数学术语；
    题干中的图片使用<img_ggb></img_ggb>包裹，内容为用geogebra语言绘制该题目图形的代码，如果题目没有图片，则不需要该标签；
    公式使用LaTeX格式并用$包裹；换行使用<br>。"""
    result = asyncio.run(call_gemini_pdf_api(pdf_path=pdf_path, prompt=prompt))
    if result:
        print("API 响应:")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    exit()

    image_name = "test.png"
    image_path = os.path.join(cur_dir, image_name)
    prompt = "\n识别出选择题页面中的印刷体题目和选项内容。要求：1、换行使用<br>；2、公式使用LaTeX格式并用$包裹；3、统一使用<blank>作为作答区标识。4、使用<option>分隔选项内容；\n## 示例：对于输入的某个图片，其输出：\"1．若 $\\vert a \\vert = 3$ , $\\vert b \\vert = 2$ ，且 $a > b$ ，则 $a + b$ 的值等于<br><blank><br><option>A.5<option>B.0<br><option>C.1<option>D.5或1\"。"
    result = asyncio.run(call_gemini_api(image_path=image_path, prompt=prompt))
    if result:
        print("API 响应:")
        print(json.dumps(result, ensure_ascii=False, indent=2))

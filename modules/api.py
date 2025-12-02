from .extractor import parse_grok, get_anim, parse_values
from .signature import generate_sign
from .crypto import generate_keys, sign_challenge
from curl_cffi import requests, CurlMime
from bs4 import BeautifulSoup
from json import dumps, loads
from uuid import uuid4

def send_request(ctx, msg, new_chat=True, chat_id=None, parent_msg=None):
    if new_chat:
        payload = {
            'temporary': False,
            'modelName': 'grok-3',
            'message': msg,
            'fileAttachments': [],
            'imageAttachments': [],
            'disableSearch': False,
            'enableImageGeneration': True,
            'returnImageBytes': False,
            'returnRawGrokInXaiRequest': False,
            'enableImageStreaming': True,
            'imageGenerationCount': 2,
            'forceConcise': False,
            'toolOverrides': {},
            'enableSideBySide': True,
            'sendFinalMetadata': True,
            'isReasoning': False,
            'webpageUrls': [],
            'disableTextFollowUps': False,
            'responseMetadata': {'requestModelDetails': {'modelId': 'grok-3'}},
            'disableMemory': False,
            'forceSideBySide': False,
            'modelMode': 'MODEL_MODE_AUTO',
            'isAsyncChat': False,
        }
        resp = ctx['session'].post('https://grok.com/rest/app-chat/conversations/new', json=payload, timeout=9999)
    else:
        payload = {
            'message': msg,
            'modelName': 'grok-3',
            'parentResponseId': parent_msg,
            'disableSearch': False,
            'enableImageGeneration': True,
            'imageAttachments': [],
            'returnImageBytes': False,
            'returnRawGrokInXaiRequest': False,
            'fileAttachments': [],
            'enableImageStreaming': True,
            'imageGenerationCount': 2,
            'forceConcise': False,
            'toolOverrides': {},
            'enableSideBySide': True,
            'sendFinalMetadata': True,
            'customPersonality': '',
            'isReasoning': False,
            'webpageUrls': [],
            'metadata': {'requestModelDetails': {'modelId': 'grok-3'}, 'request_metadata': {'model': 'grok-3', 'mode': 'auto'}},
            'disableTextFollowUps': False,
            'disableArtifact': False,
            'isFromGrokFiles': False,
            'disableMemory': False,
            'forceSideBySide': False,
            'modelMode': 'MODEL_MODE_AUTO',
            'isAsyncChat': False,
            'skipCancelCurrentInflightRequests': False,
            'isRegenRequest': False,
        }
        resp = ctx['session'].post(f'https://grok.com/rest/app-chat/conversations/{chat_id}/responses', json=payload, timeout=9999)
    return resp

def parse_response(resp):
    answer = None
    chat_id = None
    parent_msg = None
    stream_data = []
    images = []
    for text_line in resp.text.strip().split('\n'):
        try:
            parsed = loads(text_line)
            result = parsed.get('result', {})
            response = result.get('response', {})
            model_response = response.get('modelResponse', {}) or result.get('modelResponse', {})
            
            chunk = response.get('token') or result.get('token')
            if chunk:
                stream_data.append(chunk)
            
            if not answer and model_response.get('message'):
                answer = model_response.get('message')
            
            if not chat_id and result.get('conversation', {}).get('conversationId'):
                chat_id = result['conversation']['conversationId']
                
            if not parent_msg and model_response.get('responseId'):
                parent_msg = model_response.get('responseId')
                
            if model_response.get('imageAttachments'):
                for img in model_response['imageAttachments']:
                    images.append(img)
            
            if model_response.get('generatedImageUrls'):
                for img_url in model_response['generatedImageUrls']:
                    # Convert to expected format if needed, or just append dict
                    images.append({'imageUrl': img_url, 'id': str(uuid4())})

            elif "image" in text_line.lower():
                pass
        except:
            pass
    return answer, chat_id, parent_msg, stream_data, images

def setup_headers(ctx, sig_id):
    ctx['session'].headers = {
        'accept': '*/*',
        'accept-language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
        'baggage': ctx['baggage'],
        'cache-control': 'no-cache',
        'content-type': 'application/json',
        'origin': 'https://grok.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://grok.com/c',
        'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'sentry-trace': f'{ctx["sentry_trace"]}-{str(uuid4()).replace("-", "")[:16]}-0',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
        'x-statsig-id': sig_id,
        'x-xai-request-id': str(uuid4()),
    }

def start_grok_conversation(msg, proxy_url=None, session_data=None):
    ctx = create_session(proxy_url)
    if session_data:
        load_existing(ctx, session_data)
        make_request(ctx, ctx['actions'][1])
        make_request(ctx, ctx['actions'][2])
        sig_id = generate_sign(f'/rest/app-chat/conversations/{session_data["conversationId"]}/responses', 'POST', ctx['verification_token'], ctx['svg_data'], ctx['numbers'])
        setup_headers(ctx, sig_id)
        resp = send_request(ctx, msg, False, session_data["conversationId"], session_data["parentResponseId"])
        if "modelResponse" in resp.text:
            answer, chat_id, parent_msg, stream_data, images = parse_response(resp)
            return {"response": answer, "stream_response": stream_data, "images": images, "extra_data": {"anon_user": ctx['anon_user'], "cookies": ctx['session'].cookies.get_dict(), "actions": ctx['actions'], "xsid_script": ctx['xsid_script'], "baggage": ctx['baggage'], "sentry_trace": ctx['sentry_trace'], "conversationId": session_data["conversationId"], "parentResponseId": parent_msg, "privateKey": ctx['keys']["privateKey"]}}
    else:
        load_session(ctx)
        make_request(ctx, ctx['actions'][0])
        make_request(ctx, ctx['actions'][1])
        make_request(ctx, ctx['actions'][2])
        sig_id = generate_sign('/rest/app-chat/conversations/new', 'POST', ctx['verification_token'], ctx['svg_data'], ctx['numbers'])
        setup_headers(ctx, sig_id)
        resp = send_request(ctx, msg, True)
        if "modelResponse" in resp.text:
            answer, chat_id, parent_msg, stream_data, images = parse_response(resp)
            return {"response": answer, "stream_response": stream_data, "images": images, "extra_data": {"anon_user": ctx['anon_user'], "cookies": ctx['session'].cookies.get_dict(), "actions": ctx['actions'], "xsid_script": ctx['xsid_script'], "baggage": ctx['baggage'], "sentry_trace": ctx['sentry_trace'], "conversationId": chat_id, "parentResponseId": parent_msg, "privateKey": ctx['keys']["privateKey"]}}
    if 'rejected by anti-bot rules' in resp.text:
        return start_grok_conversation(msg=msg, proxy_url=proxy_url, session_data=session_data)
    print("Something went wrong")
    print(resp.text)
    return {"error": resp.text}

def make_request(ctx, cmd):
    ctx['session'].headers = {
        'accept': 'text/x-component',
        'accept-language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
        'baggage': ctx['baggage'],
        'cache-control': 'no-cache',
        'next-action': cmd,
        'next-router-state-tree': '%5B%22%22%2C%7B%22children%22%3A%5B%22c%22%2C%7B%22children%22%3A%5B%5B%22slug%22%2C%22%22%2C%22oc%22%5D%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%2Cnull%2Cnull%5D%7D%2Cnull%2Cnull%5D%7D%2Cnull%2Cnull%5D%7D%2Cnull%2Cnull%2Ctrue%5D',
        'origin': 'https://grok.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://grok.com/c',
        'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'sentry-trace': f'{ctx["sentry_trace"]}-{str(uuid4()).replace("-", "")[:16]}-0',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
    }
    if ctx['c_run'] == 0:
        form_data = CurlMime()
        form_data.addpart(name="1", data=bytes(ctx['keys']["userPublicKey"]), filename="blob", content_type="application/octet-stream")
        form_data.addpart(name="0", filename=None, data='[{"userPublicKey":"$o1"}]')
        req = ctx['session'].post("https://grok.com/c", multipart=form_data)
        ctx['session'].cookies.update(req.cookies)
        ctx['anon_user'] = req.text.split('{"anonUserId":"')[1].split('"')[0]
        ctx['c_run'] += 1
    else:
        ctx['session'].headers.update({'content-type': 'text/plain;charset=UTF-8'})
        if ctx['c_run'] == 1:
            payload = dumps([{"anonUserId": ctx['anon_user']}])
        elif ctx['c_run'] == 2:
            payload = dumps([{"anonUserId": ctx['anon_user'], **ctx['challenge_dict']}])
        req = ctx['session'].post('https://grok.com/c', data=payload)
        ctx['session'].cookies.update(req.cookies)
        if ctx['c_run'] == 1:
            challenge_data = b''
            start_pos = req.content.hex().find("3a6f38362c")
            if start_pos != -1:
                start_pos += len("3a6f38362c")
                end_pos = req.content.hex().find("313a", start_pos)
                if end_pos != -1:
                    challenge_hex = req.content.hex()[start_pos:end_pos]
                    challenge_data = bytes.fromhex(challenge_hex)
            ctx['challenge_dict'] = sign_challenge(challenge_data, ctx['keys']["privateKey"])
        elif ctx['c_run'] == 2:
            ctx['verification_token'], ctx['anim'] = get_anim(req.text, "grok-site-verification")
            ctx['svg_data'], ctx['numbers'] = parse_values(req.text, ctx['anim'], ctx['xsid_script'])
        ctx['c_run'] += 1

def create_session(proxy_url=None):
    http_client = requests.Session(impersonate="chrome136")
    http_client.headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'priority': 'u=0, i',
        'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
    }
    if proxy_url:
        http_client.proxies = {"all": proxy_url}
    return {'session': http_client, 'c_run': 0, 'keys': generate_keys(), 'actions': None, 'xsid_script': None, 'baggage': None, 'sentry_trace': None, 'anon_user': None, 'challenge_dict': None, 'verification_token': None, 'anim': None, 'svg_data': None, 'numbers': None}

def load_existing(ctx, session_data):
    ctx['session'].cookies.update(session_data["cookies"])
    ctx['actions'] = session_data["actions"]
    ctx['xsid_script'] = session_data["xsid_script"]
    ctx['baggage'] = session_data["baggage"]
    ctx['sentry_trace'] = session_data["sentry_trace"]
    ctx['c_run'] = 1
    ctx['anon_user'] = session_data["anon_user"]
    ctx['keys']["privateKey"] = session_data["privateKey"]

def load_session(ctx):
    site_resp = ctx['session'].get('https://grok.com/c')
    ctx['session'].cookies.update(site_resp.cookies)
    script_urls = [s['src'] for s in BeautifulSoup(site_resp.text, 'html.parser').find_all('script', src=True) if s['src'].startswith('/_next/static/chunks/')]
    ctx['actions'], ctx['xsid_script'] = parse_grok(script_urls)
    ctx['baggage'] = site_resp.text.split('<meta name="baggage" content="')[1].split('"')[0]
    ctx['sentry_trace'] = site_resp.text.split('<meta name="sentry-trace" content="')[1].split('-')[0]

from re import findall, search
from json import load, dump, loads
from base64 import b64decode, b64encode
from os import path
from secrets import token_bytes
from hashlib import sha256

from curl_cffi import requests
from bs4 import BeautifulSoup
from coincurve import PrivateKey

# Global state
data_map = {}
data_loaded = False
script_cache = []
cache_loaded = False

def get_anim(page_html, meta_name="grok-site-verification"):
    token = page_html.split(f'"name":"{meta_name}","content":"')[1].split('"')[0]
    token_bytes_list = list(b64decode(token))
    animation_class = "loading-x-anim-" + str(token_bytes_list[5] % 4)
    return token, animation_class

def load_xsid_mapping():
    global data_map, data_loaded
    if not data_loaded and path.exists('modules/data.json'):
        with open('modules/data.json', 'r') as f:
            data_map = load(f)
        data_loaded = True

def load_grok_mapping():
    global script_cache, cache_loaded
    if not cache_loaded and path.exists('modules/config.json'):
        with open('modules/config.json', 'r') as f:
            script_cache = load(f)
        cache_loaded = True

def parse_grok(script_urls):
    global script_cache
    load_grok_mapping()
    for cached_item in script_cache:
        if cached_item.get("action_script") in script_urls:
            return cached_item["actions"], cached_item["xsid_script"]
            
    action_content = ""
    xsid_content = ""
    action_url = ""
    
    for script_url in script_urls:
        try:
            script_text = requests.get(f'https://grok.com{script_url}', impersonate="chrome124").text
            if "anonPrivateKey" in script_text:
                action_content = script_text
                action_url = script_url
            elif "880932)" in script_text:
                xsid_content = script_text
        except Exception as e:
            print(f"Error fetching script {script_url}: {e}")
            continue
            
    if not action_content or not xsid_content:
        print("Could not find action or xsid content")
        return None, None

    action_list = findall(r'createServerReference\)\("([a-f0-9]+)"', action_content)
    xsid_match = search(r'"(static/chunks/[^"]+\.js)"[^}]*?a\(880932\)', xsid_content)
    
    if action_list and xsid_match:
        xsid_path = xsid_match.group(1)
        script_cache.append({
            "xsid_script": xsid_path,
            "action_script": action_url,
            "actions": action_list
        })
        with open('modules/config.json', 'w') as f:
            dump(script_cache, f, indent=2)
        return action_list, xsid_path
    else:
        print("Something went wrong while parsing script and actions")
        return None, None

def parse_values(page_html, anim_class="loading-x-anim-0", script_id=""):
    global data_map
    load_xsid_mapping()
    svg_paths = findall(r'"d":"(M[^"]{200,})"', page_html)
    
    try:
        path_index = int(anim_class.split("loading-x-anim-")[1])
        if path_index < len(svg_paths):
            path_data = svg_paths[path_index]
        else:
            path_data = svg_paths[0] if svg_paths else ""
    except:
        path_data = svg_paths[0] if svg_paths else ""

    if script_id:
        if script_id == "ondemand.s":
            try:
                js_url = 'https://abs.twimg.com/responsive-web/client-web/ondemand.s.' + page_html.split(f'"{script_id}":"')[1].split('"')[0] + 'a.js'
            except:
                return path_data, []
        else:
            js_url = f'https://grok.com/_next/{script_id}'
            
        if js_url in data_map:
            indices = data_map[js_url]
        else:
            try:
                js_text = requests.get(js_url, impersonate="chrome124").text
                indices = [int(x) for x in findall(r'x\[(\d+)\]\s*,\s*16', js_text)]
                data_map[js_url] = indices
                with open('modules/data.json', 'w') as f:
                    dump(data_map, f)
            except Exception as e:
                print(f"Error fetching js {js_url}: {e}")
                indices = []
                
        return path_data, indices
    else:
        return path_data

def public_key_create(private_bytes):
    priv_key = PrivateKey(bytes(private_bytes))
    pub_key = priv_key.public_key.format(compressed=True)
    return list(pub_key)

def xor(data_bytes):
    result = ""
    for i in range(len(data_bytes)):
        result += chr(data_bytes[i])
    return b64encode(result.encode('latin-1')).decode()

def generate_keys():
    raw_key = token_bytes(32)
    pub_key = public_key_create(raw_key)
    encoded_key = xor(raw_key)
    
    return {
        "privateKey": encoded_key,
        "userPublicKey": pub_key
    }

def sign_challenge(challenge_data, encoded_key):
    try:
        # Decode the key
        key_raw_str = b64decode(encoded_key).decode('latin-1')
        key_raw = bytes([ord(c) for c in key_raw_str])
        
        priv_key = PrivateKey(key_raw)
        sig = priv_key.sign_recoverable(sha256(challenge_data).digest(), hasher=None)[:64]
        
        return {
            "challenge": b64encode(challenge_data).decode(),
            "signature": b64encode(sig).decode()
        }
    except Exception as e:
        print(f"Error signing challenge: {e}")
        return None
